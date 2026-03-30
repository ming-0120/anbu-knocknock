import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.database import async_engine
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

KST = ZoneInfo("Asia/Seoul")


async def run():

    target_hour = datetime.now(KST).replace(minute=0, second=0, microsecond=0)

    query = """
    INSERT INTO hourly_features
    (
        resident_id,
        target_hour,
        x1_motion_count,
        x2_door_count,
        x6_last_motion_min
    )

    SELECT
        d.resident_id,
        :hour,

        SUM(CASE WHEN s.event_type = 'motion' THEN 1 ELSE 0 END) AS motion_cnt,

        SUM(CASE
            WHEN s.event_type = 'door_open'
              OR s.event_type = 'door_close'
            THEN 1 ELSE 0 END) AS door_cnt,

        TIMESTAMPDIFF(
            MINUTE,
            MAX(s.event_at),
            NOW()
        ) AS last_motion_min

    FROM sensor_events s
    JOIN devices d
        ON s.device_id = d.device_id

    WHERE s.event_at >= :hour
      AND s.event_at < DATE_ADD(:hour, INTERVAL 1 HOUR)

    GROUP BY d.resident_id
    """

    async with AsyncSessionLocal() as db:
        await db.execute(text(query), {"hour": target_hour})
        await db.commit()

    print("hourly feature created:", target_hour)


if __name__ == "__main__":

    async def main():
        try:
            await run()
        finally:
            await async_engine.dispose()

    asyncio.run(main())