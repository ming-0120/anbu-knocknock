import pandas as pd
from datetime import datetime, timedelta, time
from typing import List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor_event import SensorEvent
from app.models.resident_setting import ResidentSetting
from app.models.daily_feature import DailyFeature
from app.models.device import Device

async def aggregate_daily_features(db: AsyncSession, target_date: datetime.date):
    print(f"\n[START] aggregate_daily_features | target_date={target_date}")

    start_dt = datetime.combine(target_date, time.min)
    end_dt = datetime.combine(target_date, time.max)

    print(f"[STEP1] range: {start_dt} ~ {end_dt}")

    stmt = (
        select(SensorEvent, Device.resident_id)
        .join(Device, SensorEvent.device_id == Device.device_id)
        .where(SensorEvent.event_at >= start_dt, SensorEvent.event_at <= end_dt)
    )

    result = await db.execute(stmt)
    rows = result.all()

    print(f"[STEP2] fetched sensor rows: {len(rows)}")

    if not rows:
        print("[INFO] no sensor events found.")
        return 0

    df = pd.DataFrame([
        {
            "resident_id": resident_id,
            "event_type": ev.event_type,
            "event_at": ev.event_at,
        }
        for (ev, resident_id) in rows
    ])

    print(f"[STEP3] dataframe rows: {len(df)}")
    print(f"[STEP3] unique residents: {df['resident_id'].nunique()}")

    settings_stmt = select(ResidentSetting)
    settings_result = await db.execute(settings_stmt)
    settings_dict = {s.resident_id: s for s in settings_result.scalars().all()}

    print(f"[STEP4] loaded settings: {len(settings_dict)}")

    new_features: List[DailyFeature] = []

    for resident_id, group in df.groupby("resident_id"):
        print(f"\n[RESIDENT] processing resident_id={resident_id}")

        setting = settings_dict.get(resident_id)
        if not setting:
            print("  -> no setting found, skip")
            continue

        group = group.sort_values("event_at")
        motions = group[group["event_type"] == "motion"]
        doors = group[group["event_type"] == "door_close"]

        x1 = len(motions)
        x2 = len(doors)

        x3 = 0.0
        if x1 > 1:
            x3 = motions["event_at"].diff().dt.total_seconds().mean() / 60.0

        s_start = setting.sleep_start
        s_end = setting.sleep_end

        if s_start > s_end:
            night_mask = (group["event_at"].dt.time >= s_start) | (group["event_at"].dt.time <= s_end)
        else:
            night_mask = (group["event_at"].dt.time >= s_start) & (group["event_at"].dt.time <= s_end)

        x4 = len(group[night_mask & (group["event_type"] == "motion")])

        if x1 > 0:
            first_at = motions.iloc[0]["event_at"]
            x5 = first_at.hour * 60 + first_at.minute

            last_at = motions.iloc[-1]["event_at"]
            x6 = int((end_dt - last_at).total_seconds() // 60)
            x6 = max(0, min(1440, x6))
        else:
            x5 = None
            x6 = 1440

        print(f"  x1={x1}, x2={x2}, x3={round(x3,2)}, x4={x4}, x5={x5}, x6={x6}")

        new_features.append(DailyFeature(
            resident_id=resident_id,
            target_date=target_date,
            x1_motion_count=x1,
            x2_door_count=x2,
            x3_avg_interval=round(x3, 2),
            x4_night_motion_count=x4,
            x5_first_motion_min=x5,
            x6_last_motion_min=x6
        ))

    print(f"\n[STEP7] total new_features: {len(new_features)}")

    await db.execute(delete(DailyFeature).where(DailyFeature.target_date == target_date))
    print("[STEP7] deleted existing rows for target_date")

    if new_features:
        db.add_all(new_features)
        await db.flush()
        await db.commit()
        print("[STEP7] insert committed to DB")

    print("[END] aggregate_daily_features complete\n")
    return len(new_features)
# app/services/aggregator.py 맨 아래에 추가
if __name__ == "__main__":
    import asyncio
    from datetime import datetime, timedelta
    from app.db.database import AsyncSessionLocal

    async def _main():
        # 보통 어제 날짜를 집계
        # target_date = (datetime.now().date() - timedelta(days=1))
        target_date = datetime.now().date()
        print(f"[RUN] aggregator module start | target_date={target_date}")

        async with AsyncSessionLocal() as db:
            try:
                n = await aggregate_daily_features(db, target_date)
                # aggregate_daily_features 안에서 commit을 안 한다면 여기서 commit 필요
                await db.commit()
                print(f"[DONE] daily_features inserted/updated: {n}")
            except Exception as e:
                await db.rollback()
                print(f"[ERROR] {e}")
                raise

    asyncio.run(_main())