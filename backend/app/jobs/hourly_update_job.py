# app/jobs/hourly_hybrid_update_job.py
import json
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.models.hourly_feature import HourlyFeature
from app.models.risk_score import RiskScore
from app.models.resident_setting import ResidentSetting

from app.services.risk_utils import (
    LEVEL_SCORE01,
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
    - 활동량이 0이면 페널티(옵션)
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


async def run_hourly_hybrid_update(target_hour_kst: datetime | None = None) -> None:
    now_kst = datetime.now(KST)
    if target_hour_kst is None:
        target_hour_kst = now_kst.replace(minute=0, second=0, microsecond=0)

    today: date = target_hour_kst.date()

    async with AsyncSessionLocal() as db:
        # 오늘자 daily_feature + baseline risk_score(있어야 함) + setting
        stmt = (
            select(DailyFeature, RiskScore, ResidentSetting)
            .join(RiskScore, RiskScore.feature_id == DailyFeature.feature_id)
            .outerjoin(ResidentSetting, ResidentSetting.resident_id == DailyFeature.resident_id)
            .where(DailyFeature.target_date == today)
        )

        rows = (await db.execute(stmt)).all()

        for daily, risk, setting in rows:
            resident_id = int(daily.resident_id)
            feature_id = int(daily.feature_id)

            # baseline
            base = float(risk.s_base)  # 0~1

            # hourly row (해당 정각 블록)
            h = (
                await db.execute(
                    select(HourlyFeature).where(
                        and_(
                            HourlyFeature.resident_id == resident_id,
                            HourlyFeature.target_hour == target_hour_kst.replace(tzinfo=None),
                        )
                    )
                )
            ).scalar_one_or_none()

            # hourly_features가 없으면 0으로 처리
            if h is None:
                hourly_component = 0.0
                motion = door = x6 = None
            else:
                threshold_min = int(getattr(setting, "no_activity_threshold_min", None) or 60)  # 시간 단위 기본 60분(정책)
                hourly_component = compute_hourly_component01(h, threshold_min)
                motion = int(h.x1_motion_count)
                door = int(h.x2_door_count)
                x6 = int(h.x6_last_motion_min)

            # settings JSON
            cfg = parse_config(getattr(setting, "days_of_week", None))
            out, out_label = is_on_outing(cfg, target_hour_kst)

            # 외출 중이면 단기 성분 감쇄(정책)
            w_outing = 0.5 if out else 1.0
            hourly_component = clamp01(hourly_component * w_outing)

            # 질병/민감도(정책: 최종점수에 곱)
            alpha = disease_alpha(cfg)
            s_weight = float(getattr(setting, "sensitivity_weight", None) or 1.0)

            # 하이브리드 결합
            final = clamp01(W_BASE * base + W_HOURLY * hourly_component)
            final = clamp01(final * float(alpha) * float(s_weight))

            level = level_from_score01(final)

            risk.score = round(final, 4)
            risk.level = level
            risk.scored_at = target_hour_kst.astimezone(timezone.utc).replace(tzinfo=None)

            risk.reason_codes = {
                "mode": "hybrid_update",
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
    asyncio.run(run_hourly_hybrid_update())