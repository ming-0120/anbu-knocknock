import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.resident import Resident
from app.models.daily_feature import DailyFeature


DAYS = 30


def make_features(risk_type: str):
    """
    위험도 유형별 feature 생성
    """

    if risk_type == "high":
        return {
            "x1_motion_count": random.randint(5, 20),
            "x2_door_count": random.randint(0, 1),
            "x3_avg_interval": random.uniform(200, 600),
            "x4_night_motion_count": random.randint(3, 10),
            "x5_first_motion_min": random.randint(200, 400),
            "x6_last_motion_min": random.randint(200, 600),
        }

    if risk_type == "normal":
        return {
            "x1_motion_count": random.randint(30, 80),
            "x2_door_count": random.randint(1, 3),
            "x3_avg_interval": random.uniform(60, 200),
            "x4_night_motion_count": random.randint(1, 3),
            "x5_first_motion_min": random.randint(60, 120),
            "x6_last_motion_min": random.randint(60, 120),
        }

    return {
        "x1_motion_count": random.randint(80, 150),
        "x2_door_count": random.randint(3, 6),
        "x3_avg_interval": random.uniform(10, 60),
        "x4_night_motion_count": random.randint(0, 1),
        "x5_first_motion_min": random.randint(10, 40),
        "x6_last_motion_min": random.randint(10, 40),
    }


async def run():

    async with AsyncSessionLocal() as db:

        residents = (
            await db.execute(select(Resident.resident_id))
        ).scalars().all()

        total = len(residents)

        high_cnt = int(total * 0.30)
        normal_cnt = int(total * 0.20)
        safe_cnt = total - high_cnt - normal_cnt

        risk_types = (
            ["high"] * high_cnt
            + ["normal"] * normal_cnt
            + ["safe"] * safe_cnt
        )

        random.shuffle(risk_types)

        today = date.today()

        rows = []

        for idx, resident_id in enumerate(residents):

            risk_type = risk_types[idx]

            for d in range(DAYS):

                target_date = today - timedelta(days=d)

                f = make_features(risk_type)

                rows.append(
                    DailyFeature(
                        resident_id=resident_id,
                        target_date=target_date,
                        x1_motion_count=f["x1_motion_count"],
                        x2_door_count=f["x2_door_count"],
                        x3_avg_interval=f["x3_avg_interval"],
                        x4_night_motion_count=f["x4_night_motion_count"],
                        x5_first_motion_min=f["x5_first_motion_min"],
                        x6_last_motion_min=f["x6_last_motion_min"],
                    )
                )

        db.add_all(rows)

        await db.commit()

        print("daily_features created:", len(rows))


if __name__ == "__main__":
    asyncio.run(run())