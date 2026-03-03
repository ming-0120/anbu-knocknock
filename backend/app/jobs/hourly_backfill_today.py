import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.database import AsyncSessionLocal, async_engine
from app.services.hourly_aggregator import aggregate_hourly_features

KST = ZoneInfo("Asia/Seoul")

async def main():
    now = datetime.now(KST)
    cur_hour = now.replace(minute=0, second=0, microsecond=0)
    start = cur_hour.replace(hour=0)

    total = 0
    async with AsyncSessionLocal() as db:
        try:
            h = start
            while h <= cur_hour:
                n = await aggregate_hourly_features(db, h.replace(tzinfo=None))
                total += n
                h += timedelta(hours=1)
            await db.commit()
            print(f"[DONE] hourly_features rows inserted today total={total}")
        except Exception:
            await db.rollback()
            raise
        finally:
            await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())