import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, Optional, Tuple
from app.models.device import Device
from zoneinfo import ZoneInfo
from sqlalchemy import select, func, and_, update

from app.db.database import AsyncSessionLocal
from app.models.resident import Resident
from app.models.daily_feature import DailyFeature
from app.models.risk_score import RiskScore
from app.models.resident_setting import ResidentSetting

# ⚠️ 아래 SensorEvent 모델/컬럼은 프로젝트에 맞게 수정 필요
# 예: event_at 컬럼명, event_type 컬럼명, resident_id 직접 있는지 등
from app.models.sensor_event import SensorEvent  # <- 실제 경로/모델명으로 교체

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
WEEKDAY_MAP = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}

# --- 합성 가중치(정책값): 필요하면 바꾸면 됨 ---
W_BASE = 0.7     # 새벽 4시 베이스라인(14일 학습 결과)
W_HOURLY = 0.3   # 최근 1시간 패턴
# ---------------------------------------------

@dataclass
class HourlySignals:
    motion_count: int
    door_count: int
    last_event_at: Optional[datetime]
    inactive_minutes: Optional[int]
    
async def fetch_hourly_signals_from_sensor_events_join_device(
    session,
    resident_id: int,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> HourlySignals:
    """
    sensor_events에는 resident_id가 없으므로 devices와 조인해서 resident_id 기준으로 집계.
    """

    # ✅ 프로젝트 기준 event_type 문자열로 수정
    MOTION_TYPES = ("motion",)
    DOOR_TYPES = ("door_open", "door_close", "door")

    # CASE 집계 (SQLAlchemy 2.x 호환)
    motion_case = func.sum(func.case((SensorEvent.event_type.in_(MOTION_TYPES), 1), else_=0))
    door_case = func.sum(func.case((SensorEvent.event_type.in_(DOOR_TYPES), 1), else_=0))

    stmt = (
        select(
            motion_case.label("motion_count"),
            door_case.label("door_count"),
            func.max(SensorEvent.event_at).label("last_event_at"),
        )
        .select_from(SensorEvent)
        .join(Device, SensorEvent.device_id == Device.device_id)  # ⚠️ 키 컬럼명 맞추기
        .where(
            and_(
                Device.resident_id == resident_id,
                SensorEvent.event_at >= window_start_utc,
                SensorEvent.event_at < window_end_utc,
            )
        )
    )

    row = (await session.execute(stmt)).one()
    motion_count = int(row.motion_count or 0)
    door_count = int(row.door_count or 0)
    last_event_at = row.last_event_at

    inactive_minutes: Optional[int] = None
    if last_event_at is not None:
        if last_event_at.tzinfo is None:
            last_event_at = last_event_at.replace(tzinfo=timezone.utc)
        diff_sec = (window_end_utc - last_event_at).total_seconds()
        if diff_sec < 0:
            diff_sec = 0
        inactive_minutes = int(diff_sec // 60)

    return HourlySignals(
        motion_count=motion_count,
        door_count=door_count,
        last_event_at=last_event_at,
        inactive_minutes=inactive_minutes,
    )

def _round_down_to_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _parse_json(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _time_in_range(start_hhmm: str, end_hhmm: str, now_kst: datetime) -> bool:
    """23:00~02:00 같은 자정 넘어가는 구간까지 처리."""
    current = now_kst.time()
    start = datetime.strptime(start_hhmm, "%H:%M").time()
    end = datetime.strptime(end_hhmm, "%H:%M").time()

    if start <= end:
        return start <= current <= end
    return (current >= start) or (current <= end)


def is_on_outing(days_of_week_json: Dict[str, Any], now_kst: datetime) -> Tuple[bool, str]:
    """
    days_of_week 예시:
    {
      "health": {"diseases": []},
      "routine": {"outings":[{"days":["TUE","WED"],"label":"산책","schedule":[{"start":"10:00","end":"11:00"}]}]}
    }
    """
    routine = (days_of_week_json.get("routine") or {})
    outings = routine.get("outings") or []
    day = WEEKDAY_MAP.get(now_kst.weekday(), "")

    for outing in outings:
        if day not in (outing.get("days") or []):
            continue
        for sch in (outing.get("schedule") or []):
            s = sch.get("start")
            e = sch.get("end")
            if not s or not e:
                continue
            if _time_in_range(s, e, now_kst):
                return True, outing.get("label", "정기 외출")
    return False, ""


def clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def level_from_score(score01: float) -> str:
    # 기존 Enum: normal/watch/alert/emergency
    if score01 >= 1.0:
        return "emergency"
    if score01 >= 0.8:
        return "alert"
    if score01 >= 0.5:
        return "watch"
    return "normal"


async def fetch_hourly_signals_from_sensor_events(
    session,
    resident_id: int,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> HourlySignals:
    """
    최근 1시간 window에서 sensor_events를 집계.
    ⚠️ event_type 값은 프로젝트 기준으로 교체해야 함.
    - 모션: "motion"
    - 문열림/닫힘: "door_open"/"door_close" 또는 "door"
    """
    # ✅ 프로젝트 기준 event_type 문자열로 수정
    MOTION_TYPES = ("motion",)
    DOOR_TYPES = ("door_open", "door_close", "door")

    # ⚠️ SensorEvent에 resident_id가 없다면 Device 조인이 필요함.
    # (네 프로젝트가 resident별로 이벤트가 들어온다고 가정하면 아래 그대로 사용)
    stmt = (
        select(
            func.sum(func.case((SensorEvent.event_type.in_(MOTION_TYPES), 1), else_=0)).label("motion_count"),
            func.sum(func.case((SensorEvent.event_type.in_(DOOR_TYPES), 1), else_=0)).label("door_count"),
            func.max(SensorEvent.event_at).label("last_event_at"),
        )
        .where(
            and_(
                SensorEvent.resident_id == resident_id,          # ⚠️ 없으면 조인으로 대체
                SensorEvent.event_at >= window_start_utc,
                SensorEvent.event_at < window_end_utc,
            )
        )
    )

    row = (await session.execute(stmt)).one()
    motion_count = int(row.motion_count or 0)
    door_count = int(row.door_count or 0)
    last_event_at = row.last_event_at

    inactive_minutes: Optional[int] = None
    if last_event_at is not None:
        # last_event_at이 naive면 UTC로 간주(프로젝트 설정에 따라 바꿔야 함)
        if last_event_at.tzinfo is None:
            last_event_at = last_event_at.replace(tzinfo=timezone.utc)
        diff_sec = (window_end_utc - last_event_at).total_seconds()
        if diff_sec < 0:
            diff_sec = 0
        inactive_minutes = int(diff_sec // 60)

    return HourlySignals(
        motion_count=motion_count,
        door_count=door_count,
        last_event_at=last_event_at,
        inactive_minutes=inactive_minutes,
    )


def compute_hourly_component(signals: HourlySignals, threshold_min: int) -> float:
    """
    최근 1시간 성분을 0~1로 만듦.
    - 기본은 '비활동(inactive) 기반' + '저활동(motion/door) 페널티'의 단순 결합 예시.
    - 정확한 수식이 너희가 정한 게 있으면 여길 교체하면 됨.
    """
    # 1) 비활동 기반 (threshold 대비 비율)
    if signals.inactive_minutes is None:
        inactive_ratio = 0.0
    else:
        inactive_ratio = min(signals.inactive_minutes / float(max(threshold_min, 1)), 1.0)

    # 2) 저활동 페널티(예시): 1시간 동안 모션/도어가 거의 없으면 약간 올림
    # (정책값. 필요하면 없애거나 조정)
    activity = signals.motion_count + signals.door_count
    low_activity_penalty = 0.0
    if activity == 0:
        low_activity_penalty = 0.2
    elif activity <= 2:
        low_activity_penalty = 0.1

    return clamp01(inactive_ratio + low_activity_penalty)


async def hourly_update_risk_scores() -> None:
    """
    매 정각 실행:
    - 오늘 daily_features 기반으로 (feature_id 확보)
    - 새벽 4시에 생성된 risk_scores(베이스라인 row)를 찾아서
    - 최근 1시간 패턴 + 개인 설정(외출 루틴 등) 반영
    - risk_scores.score를 UPDATE
    """
    now_kst = datetime.now(KST)
    target_hour_kst = _round_down_to_hour(now_kst)          # 정각 기준
    window_start_kst = target_hour_kst - timedelta(hours=1)

    # UTC 변환(센서 이벤트가 UTC 저장이라면 이 방식 권장)
    window_start_utc = window_start_kst.astimezone(timezone.utc)
    window_end_utc = target_hour_kst.astimezone(timezone.utc)

    today_kst: date = target_hour_kst.date()

    logger.info(f"🕛 [정각 UPDATE] target_hour(KST)={target_hour_kst.isoformat()} window={window_start_kst.isoformat()}~{target_hour_kst.isoformat()}")

    async with AsyncSessionLocal() as session:
        # 1) 오늘자 daily_feature + risk_score + setting을 한 번에 가져오기
        # 전제: 새벽 4시 배치가 오늘자 daily_feature를 만들어둠
        stmt = (
            select(
                Resident.resident_id,
                Resident.name,
                DailyFeature.feature_id,
                RiskScore.risk_id,
                RiskScore.s_base,
                RiskScore.score.label("current_score"),
                RiskScore.level.label("current_level"),
                ResidentSetting.no_activity_threshold_min,
                ResidentSetting.days_of_week,
            )
            .join(DailyFeature, and_(
                DailyFeature.resident_id == Resident.resident_id,
                DailyFeature.target_date == today_kst,
            ))
            .join(RiskScore, RiskScore.feature_id == DailyFeature.feature_id)
            .outerjoin(ResidentSetting, ResidentSetting.resident_id == Resident.resident_id)
        )

        rows = (await session.execute(stmt)).all()
        if not rows:
            logger.warning("오늘자 daily_features 또는 risk_scores가 없어 UPDATE 대상이 없습니다. (새벽 4시 배치 선행 필요)")
            return

        updated = 0

        for row in rows:
            resident_id = row.resident_id
            name = row.name
            feature_id = row.feature_id
            base = float(row.s_base)  # Numeric -> float
            threshold_min = int(row.no_activity_threshold_min or 1440)

            # 2) 개인 루틴(외출) 확인: 외출 중이면 점수 정책 선택
            routine_json = _parse_json(row.days_of_week)
            is_out, outing_label = is_on_outing(routine_json, target_hour_kst)

            # 정책: 외출 중이면 hourly 성분을 0으로 두고 base만 반영(오탐 방지)
            if is_out:
                hourly_component = 0.0
                reason = {
                    "policy": "outing_base_only",
                    "outing_label": outing_label,
                    "base": base,
                    "hourly_component": hourly_component,
                    "threshold_min": threshold_min,
                    "window_start_utc": window_start_utc.isoformat(),
                    "window_end_utc": window_end_utc.isoformat(),
                }
            else:
                # 3) 최근 1시간 sensor_events 집계
                signals = await fetch_hourly_signals_from_sensor_events_join_device(
                    session=session,
                    resident_id=resident_id,
                    window_start_utc=window_start_utc,
                    window_end_utc=window_end_utc,
                )
                hourly_component = compute_hourly_component(signals, threshold_min)

                reason = {
                    "policy": "base_plus_hourly",
                    "base": base,
                    "hourly_component": hourly_component,
                    "threshold_min": threshold_min,
                    "motion_count": signals.motion_count,
                    "door_count": signals.door_count,
                    "inactive_minutes": signals.inactive_minutes,
                    "last_event_at": signals.last_event_at.isoformat() if signals.last_event_at else None,
                    "window_start_utc": window_start_utc.isoformat(),
                    "window_end_utc": window_end_utc.isoformat(),
                }

            # 4) 최종 합성(0~1)
            final_score = clamp01(W_BASE * base + W_HOURLY * hourly_component)
            final_level = level_from_score(final_score)

            # 5) UPDATE (feature_id 기준 1행 갱신 전제)
            upd = (
                update(RiskScore)
                .where(RiskScore.feature_id == feature_id)
                .values(
                    score=final_score,
                    level=final_level,
                    reason_codes=reason,
                    scored_at=target_hour_kst.replace(tzinfo=None),  # DB가 naive DATETIME이면 이렇게 저장
                )
            )
            await session.execute(upd)
            updated += 1

            # (선택) 고위험만 로그
            if final_level in ("alert", "emergency"):
                logger.warning(f"🚨 {name}({resident_id}) level={final_level} score={final_score:.4f}")

        await session.commit()
        logger.info(f"✅ UPDATE 완료: {updated}명 (오늘 {today_kst})")


if __name__ == "__main__":
    asyncio.run(hourly_update_risk_scores())