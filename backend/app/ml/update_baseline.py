import asyncio
import pandas as pd
from datetime import datetime

from sqlalchemy import select, delete
from app.db.database import AsyncSessionLocal
from app.models.daily_feature import DailyFeature
from app.models.resident_baseline import ResidentBaseline


async def main():

    async with AsyncSessionLocal() as db:

        stmt = select(DailyFeature)
        rows = (await db.execute(stmt)).scalars().all()

        data = []

        for r in rows:

            span = max(
                0,
                (r.x6_last_motion_min or 0) -
                (r.x5_first_motion_min or 0)
            )

            data.append({
                "resident_id": r.resident_id,
                "motion": float(r.x1_motion_count or 0),
                "night": float(r.x4_night_motion_count or 0),
                "span": span
            })

        df = pd.DataFrame(data)

        grouped = df.groupby("resident_id").agg(
            motion_mean=("motion","mean"),
            motion_std=("motion","std"),
            night_mean=("night","mean"),
            night_std=("night","std"),
            span_mean=("span","mean"),
            span_std=("span","std")
        ).reset_index()

        await db.execute(delete(ResidentBaseline))

        objs = []

        for _, r in grouped.iterrows():

            objs.append(
                ResidentBaseline(
                    resident_id=int(r.resident_id),
                    motion_mean=float(r.motion_mean or 0),
                    motion_std=float(r.motion_std or 1),
                    night_mean=float(r.night_mean or 0),
                    night_std=float(r.night_std or 1),
                    span_mean=float(r.span_mean or 0),
                    span_std=float(r.span_std or 1),
                    updated_at=datetime.utcnow()
                )
            )

        db.add_all(objs)
        await db.commit()

    print("baseline updated")


if __name__ == "__main__":
    asyncio.run(main())