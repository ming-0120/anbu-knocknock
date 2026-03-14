# Redis > sensor_events DB
import asyncio
import redis.asyncio as redis
from datetime import datetime
from app.db.database import AsyncSessionLocal
from app.models.sensor_event import SensorEvent

QUEUE = "sensor_queue"
redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

async def process(payload):

    async with AsyncSessionLocal() as db:

        event = SensorEvent(
            device_id=payload["device_id"],
            sensor_type=payload["sensor_type"],
            event_time=datetime.fromisoformat(payload["ts"])
        )

        db.add(event)
        await db.commit()

async def worker():

    while True:

        data = await redis_client.lpop(QUEUE)

        if not data:
            await asyncio.sleep(0.1)
            continue

        payload = eval(data)
        await process(payload)

async def run_worker(n=4):

    tasks = [asyncio.create_task(worker()) for _ in range(n)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(run_worker())