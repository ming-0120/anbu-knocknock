# score = 0.7*s_base + 0.3*hourly_component
import json
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, async_engine
from app.models.daily_feature import DailyFeature
from app.models.hourly_feature import HourlyFeature
from app.models.risk_score import RiskScore
from app.models.resident_setting import ResidentSetting

from app.services.risk_utils import (
    clamp01,
    parse_config,
    is_on_outing,
    disease_alpha,
)

KST = ZoneInfo("Asia/Seoul")

W_BASE = 0.7
W_HOURLY = 0.3


def level_from_score01(x: float) -> str:
    if x >= 0.95:
        return "emergency"
    if x >= 0.80:
        return "alert"
    if x >= 0.50:
        return "watch"
    return "normal"


def compute_hourly_component01(h: HourlyFeature, threshold_min: int) -> float:
    """
    hourly_features 기반 단기 위험도(0~1)
    - x6_last_motion_min: 마지막 모션 이후 경과 분
    - 활동량이 0이면 페널티
    """
    x6 = float(h.x6_last_motion_min or 0)
    inactive_ratio = min(x6 / float(max(threshold_min, 1)), 1.0)

    activity = int(h.x1_motion_count or 0) + int(h.x2_door_count or 0)
    penalty = 0.0
    if activity == 0:
        penalty = 0.20
    elif activity <= 2:
        penalty = 0.10

    return clamp01(inactive_ratio + penalty)


def _safe_parse_config(raw) -> dict:
    """
    ResidentSetting.days_of_week(혹은 config 컬럼)가
    - dict(JSON) / str(JSON) / None 등으로 섞여있을 때 안전 파싱
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


async def run_hourly_update(target_hour_kst: datetime | None = None) -> None:
    """
    [중요] INSERT(업서트) 없음. 기존 RiskScore row만 UPDATE.
    - 대상: 오늘자 daily_features 중 risk_scores가 이미 존재하는 것만
    """
    now_kst = datetime.now(KST)
    if target_hour_kst is None:
        target_hour_kst = now_kst.replace(minute=0, second=0, microsecond=0)

    today: date = target_hour_kst.date()

    # scored_at: UTC naive로 저장(기존 스키마 datetime naive 가정)
    scored_at_utc_naive = target_hour_kst.astimezone(timezone.utc).replace(tzinfo=None)

    async with AsyncSessionLocal() as db:
        # ✅ baseline(risk_scores) 존재하는 대상만 가져옴 (INSERT 경로 제거)
        stmt = (
            select(DailyFeature, RiskScore, ResidentSetting)
            .join(RiskScore, RiskScore.feature_id == DailyFeature.feature_id)
            .outerjoin(ResidentSetting, ResidentSetting.resident_id == DailyFeature.resident_id)
            .where(DailyFeature.target_date == today)
        )
        rows = (await db.execute(stmt)).all()

        if not rows:
            return

        for daily, risk, setting in rows:
            resident_id = int(daily.resident_id)

            # baseline 유지
            base = float(risk.s_base or 0.0)

            # hourly_features: 해당 정각 블록 (DB에는 naive로 저장되어 있다고 가정)
            target_hour_naive = target_hour_kst.replace(tzinfo=None)

            h = (
                await db.execute(
                    select(HourlyFeature).where(
                        and_(
                            HourlyFeature.resident_id == resident_id,
                            HourlyFeature.target_hour == target_hour_naive,
                        )
                    )
                )
            ).scalar_one_or_none()

            if h is None:
                hourly_component = 0.0
                motion = door = x6 = None
            else:
                threshold_min = int(getattr(setting, "no_activity_threshold_min", None) or 60)
                hourly_component = compute_hourly_component01(h, threshold_min)
                motion = int(h.x1_motion_count or 0)
                door = int(h.x2_door_count or 0)
                x6 = int(h.x6_last_motion_min or 0)

            # settings JSON 파싱(안전)
            raw_cfg = getattr(setting, "days_of_week", None)
            cfg = _safe_parse_config(raw_cfg)

            # 기존 유틸을 쓰되, cfg가 dict임을 보장
            # (parse_config가 별도 스키마 변환을 한다면 그걸 쓰고, 아니면 cfg 그대로)
            try:
                cfg = parse_config(cfg)  # parse_config가 dict를 받는 케이스 대응
            except Exception:
                # parse_config가 str 전용이면 여기로 떨어질 수 있음 -> cfg 그대로 진행
                pass

            out, out_label = is_on_outing(cfg, target_hour_kst)

            # 외출 중이면 단기성분 감쇄
            w_outing = 0.5 if out else 1.0
            hourly_component = clamp01(hourly_component * w_outing)

            # 질병/민감도
            alpha = float(disease_alpha(cfg) or 1.0)
            s_weight = float(getattr(setting, "sensitivity_weight", None) or 1.0)

            # 하이브리드 결합
            final = clamp01(W_BASE * base + W_HOURLY * hourly_component)
            final = clamp01(final * alpha * s_weight)

            level = level_from_score01(final)

            risk.score = round(final, 4)
            risk.level = level
            risk.scored_at = scored_at_utc_naive
            risk.reason_codes = {
                "mode": "hourly_update",
                "target_hour_kst": target_hour_kst.isoformat(),
                "base_s": round(base, 4),
                "hourly_component": round(hourly_component, 4),
                "weights": {"W_BASE": W_BASE, "W_HOURLY": W_HOURLY},
                "outing": {"is_outing": out, "label": out_label, "w_outing": w_outing},
                "health": {"alpha_disease": round(alpha, 3)},
                "sensitivity_weight": round(s_weight, 3),
                "hourly_features": {"motion": motion, "door": door, "x6_last_motion_min": x6},
                "final": round(final, 4),
            }

        await db.commit()


if __name__ == "__main__":
    import asyncio

    async def main():
        try:
            await run_hourly_update()
        finally:
            # 이벤트 루프 살아있을 때 정리 (RuntimeError: Event loop is closed 방지)
            await async_engine.dispose()

    asyncio.run(main())