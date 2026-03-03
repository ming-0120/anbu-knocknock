import asyncio
from datetime import datetime, date, time, timedelta

import numpy as np
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.models.hourly_feature import HourlyFeature  # 실제 경로/클래스명 맞추기
from app.models.resident import Resident             # residents에서 대상 가져오려면 (경로 다르면 수정)

SEED = 123


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def infer_is_high_risk(d: DailyFeature) -> bool:
    """
    daily 합성 로직(정상 vs 고위험)과 일관되게 판정하기 위한 휴리스틱.
    라벨 컬럼이 따로 있으면 그걸 쓰는 게 정석이지만, 현재는 없으니 daily 값 기반으로 추정.
    """
    return (
        d.x1_motion_count <= 50
        and d.x2_door_count <= 2
        and d.x6_last_motion_min >= 360
    )


def hour_weights(is_high_risk: bool) -> np.ndarray:
    """
    24시간 분배 가중치(합=1).
    - 정상: 07~22시에 집중
    - 고위험: 전체적으로 더 '평평'하고(혹은 특정 구간만 약간), 총량 자체는 daily에서 이미 낮게 나옴
    """
    w = np.zeros(24, dtype=float)

    if not is_high_risk:
        for h in range(24):
            w[h] = 1.0 if 7 <= h <= 22 else 0.2
    else:
        for h in range(24):
            w[h] = 0.6 if 10 <= h <= 18 else 0.4

    w = w / w.sum()
    return w


def split_counts(total: int, weights: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    total = max(0, int(total))
    return rng.multinomial(total, weights)


async def build_hourly_for_resident(
    db: AsyncSession,
    resident_id: int,
    start_date: date,
    total_days: int,
    purge_existing: bool = True,
):
    end_date = start_date + timedelta(days=total_days - 1)

    # 1) daily 로드
    stmt = (
        select(DailyFeature)
        .where(
            DailyFeature.resident_id == resident_id,
            DailyFeature.target_date >= start_date,
            DailyFeature.target_date <= end_date,
        )
        .order_by(DailyFeature.target_date.asc())
    )
    res = await db.execute(stmt)
    dailies = res.scalars().all()

    if not dailies:
        print(f"⚠️ {resident_id}: daily_features가 없습니다. (start_date/기간/시드 여부 확인)")
        return

    # 2) 기존 hourly 삭제 (target_hour는 datetime(naive)로 범위 삭제)
    if purge_existing:
        start_dt = datetime.combine(start_date, time(0, 0))                 # naive
        end_dt = datetime.combine(end_date + timedelta(days=1), time(0, 0)) # naive (exclusive)
        await db.execute(
            delete(HourlyFeature).where(
                HourlyFeature.resident_id == resident_id,
                HourlyFeature.target_hour >= start_dt,
                HourlyFeature.target_hour < end_dt,
            )
        )

    # 3) 생성
    rng = np.random.default_rng(SEED + int(resident_id))
    rows = []

    for d in dailies:
        is_high = infer_is_high_risk(d)
        w = hour_weights(is_high)

        motion_by_hour = split_counts(d.x1_motion_count, w, rng)
        door_by_hour = split_counts(d.x2_door_count, w, rng)

        # x6_last_motion_min은 "해당 시점 기준 마지막 모션 이후 경과"로 해석 가능.
        # 여기서는 하루가 갈수록 증가하도록(현실적) 만들고, daily의 x6를 상한으로 사용.
        # - 정상일: 하루 끝에 x6가 작게 남는 경향
        # - 고위험일: 하루 끝에도 x6가 크게 남는 경향 (daily 자체가 크게 생성됨)
        daily_x6 = float(clamp(d.x6_last_motion_min, 0, 1440))

        # 시간별 x6를 "선형 증가 + 약간 노이즈"로 생성 (0~daily_x6 범위)
        # h=0 -> 0 근처, h=23 -> daily_x6 근처
        for h in range(24):
            target_hour = datetime(d.target_date.year, d.target_date.month, d.target_date.day, h, 0)  # naive
            base = (daily_x6 * (h / 23.0)) if 23 > 0 else 0.0
            noise = rng.normal(0, max(5.0, daily_x6 * 0.05))
            x6_h = float(clamp(base + noise, 0.0, daily_x6))

            rows.append(
                HourlyFeature(
                    resident_id=resident_id,
                    target_hour=target_hour,
                    x1_motion_count=int(motion_by_hour[h]),
                    x2_door_count=int(door_by_hour[h]),
                    x6_last_motion_min=int(round(x6_h)),
                )
            )

    db.add_all(rows)


async def build_hourly_all_residents(start_date: date, total_days: int = 60):
    async with AsyncSessionLocal() as db:
        # residents 전원 대상 (daily가 없는 resident는 스킵 메시지)
        res = await db.execute(select(Resident.resident_id))
        resident_ids = res.scalars().all()

        if not resident_ids:
            print("⚠️ residents 테이블에 대상이 없습니다.")
            return

        for r_id in resident_ids:
            await build_hourly_for_resident(db, r_id, start_date=start_date, total_days=total_days)

        await db.commit()
        print(f"✅ hourly_features 생성 완료: resident={len(resident_ids)}명, 인당 최대 {total_days}×24={total_days*24}행")


if __name__ == "__main__":
    asyncio.run(build_hourly_all_residents(start_date=date(2026, 2, 3), total_days=60))