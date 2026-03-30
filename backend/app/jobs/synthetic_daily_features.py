import asyncio
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.models.resident import Resident  # residents에서 id 가져오려고 (경로가 다르면 수정)

TOTAL_DAYS = 60
HIGH_RISK_RATIO = 0.2  # 8:2
SEED = 42


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def make_daily_row(resident_id: int, target_date: date, is_high_risk: bool, rng: np.random.Generator) -> DailyFeature:
    """
    train_model.py에서 사용하는 daily 컬럼(당신 코드 기준):
      x1_motion_count, x2_door_count, x3_avg_interval, x4_night_motion_count,
      x5_first_motion_min, x6_last_motion_min
    """
    if not is_high_risk:
        # 정상
        x1 = int(clamp(rng.normal(120, 30), 20, 300))
        x2 = int(clamp(rng.normal(6, 2), 0, 20))
        x3 = float(clamp(rng.normal(8, 4), 0, 120))
        x4 = int(clamp(rng.normal(10, 5), 0, 60))
        x5 = float(clamp(rng.normal(480, 90), 0, 1440))   # 08:00 근처
        x6 = float(clamp(rng.normal(90, 60), 0, 1440))    # 마지막 활동 이후 경과
    else:
        # 고위험(활동↓, 출입↓, 무활동간격↑, 첫 활동 늦음, 마지막 경과↑)
        x1 = int(clamp(rng.normal(25, 15), 0, 120))
        x2 = int(clamp(rng.normal(1, 1), 0, 6))
        x3 = float(clamp(rng.normal(120, 80), 0, 1440))
        x4 = int(clamp(rng.normal(2, 3), 0, 30))
        x5 = float(clamp(rng.normal(780, 120), 0, 1440))  # 13:00 근처
        x6 = float(clamp(rng.normal(600, 200), 0, 1440))  # 마지막 경과 큼

    return DailyFeature(
        resident_id=resident_id,
        target_date=target_date,
        x1_motion_count=x1,
        x2_door_count=x2,
        x3_avg_interval=x3,
        x4_night_motion_count=x4,
        x5_first_motion_min=x5,
        x6_last_motion_min=x6,
    )


async def seed_daily_for_resident(
    db: AsyncSession,
    resident_id: int,
    start_date: date,
    total_days: int = TOTAL_DAYS,
    high_risk_ratio: float = HIGH_RISK_RATIO,
    purge_existing: bool = True,
):
    rng = np.random.default_rng(SEED + int(resident_id))

    high_n = int(round(total_days * high_risk_ratio))  # 60*0.2=12
    normal_n = total_days - high_n                     # 48
    if high_n + normal_n != total_days:
        raise ValueError("high_n/normal_n 계산 오류")

    high_days = set(rng.choice(total_days, size=high_n, replace=False).tolist())

    end_date = start_date + timedelta(days=total_days - 1)

    if purge_existing:
        await db.execute(
            delete(DailyFeature).where(
                DailyFeature.resident_id == resident_id,
                DailyFeature.target_date >= start_date,
                DailyFeature.target_date <= end_date,
            )
        )

    rows = []
    for i in range(total_days):
        d = start_date + timedelta(days=i)
        rows.append(make_daily_row(resident_id, d, is_high_risk=(i in high_days), rng=rng))

    db.add_all(rows)


async def seed_daily_all_residents(start_date: date, total_days: int = TOTAL_DAYS):
    async with AsyncSessionLocal() as db:
        # residents에서 전원 대상 (daily에 아직 없어도 가능)
        res = await db.execute(select(Resident.resident_id))
        resident_ids = res.scalars().all()

        if not resident_ids:
            print("⚠️ residents 테이블에 대상이 없습니다.")
            return

        for r_id in resident_ids:
            await seed_daily_for_resident(db, r_id, start_date=start_date, total_days=total_days)

        await db.commit()
        high_n = int(round(total_days * HIGH_RISK_RATIO))
        print(f"✅ daily_features 합성 완료: resident={len(resident_ids)}명, 인당 {total_days}일 (고위험 {high_n}일 / 정상 {total_days-high_n}일)")


if __name__ == "__main__":
    asyncio.run(seed_daily_all_residents(start_date=date(2026, 2, 3), total_days=60))