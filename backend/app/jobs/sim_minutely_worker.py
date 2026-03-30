# 센서 이벤트 생성 → Redis queue push
import asyncio
import random
from datetime import datetime, timezone, timedelta
import redis.asyncio as redis
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

KST = timezone(timedelta(hours=9))

REDIS_URL = "redis://localhost:6379"
QUEUE = "sensor_queue"

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def generate_behavior():
    r = random.random()

    if r < 0.7:
        motion = random.randint(3, 10)
        door = random.randint(0, 3)

    elif r < 0.9:
        motion = random.randint(0, 2)
        door = 0

    else:
        motion = 0
        door = 0

    return motion, door

async def get_device_ids():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT device_id FROM devices"))
        rows = result.fetchall()
        return [r[0] for r in rows]

async def push_event(device_id, sensor_type):
    payload = {
        "device_id": device_id,
        "sensor_type": sensor_type,
        "ts": datetime.now(KST).isoformat()
    }
    await redis_client.rpush(QUEUE, str(payload))

async def simulate(device_ids):
    for device_id in device_ids:

        motion, door = generate_behavior()

        for _ in range(motion):
            await push_event(device_id, "motion")

        for _ in range(door):
            await push_event(device_id, "door")

async def run():
    device_ids = await get_device_ids()

    while True:
        await simulate(device_ids)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run())