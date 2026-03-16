import asyncio
import random
import subprocess
import sys
from datetime import datetime

import redis

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.core.config import get_settings


settings = get_settings()

engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

redis_client = redis.Redis(host="localhost", port=6379, db=0)


# ------------------------
# bucket 계산 (1분으로 단축 - 빠른 테스트용)
# ------------------------
def get_bucket():
    now = datetime.now()
    # 💡 테스트를 위해 5분이 아닌 1분 단위 버킷으로 생성합니다.
    bucket = now.replace(second=0, microsecond=0)
    return bucket.strftime("%Y%m%d%H%M")


# ------------------------
# fake sensor event
# ------------------------
async def generate_fake_sensor():
    bucket = get_bucket()
    async with async_session() as db:
        result = await db.execute(text("SELECT resident_id FROM residents"))
        residents = result.fetchall()

    for row in residents:
        rid = row[0]
        key = f"sensor:{rid}:{bucket}"
        rand_val = random.random()

        # motion 이벤트
        if rand_val < 0.7:
            redis_client.hincrby(key, "motion_count", random.randint(1,3))

        # door 이벤트
        if rand_val < 0.1:
            redis_client.hincrby(key, "door_count", 1)

        redis_client.expire(key, 600)


# ------------------------
# Redis → DB 집계
# ------------------------
async def aggregate_sensor():
    bucket = get_bucket()
    keys = redis_client.keys(f"sensor:*:{bucket}")

    if not keys:
        return

    print("aggregating bucket:", bucket)
    now_time = datetime.now()
    target_hour = now_time.replace(minute=0, second=0, microsecond=0)
    current_minute = now_time.minute

    # 🔥 낮/밤 판별 (밤 22시 ~ 아침 6시)
    is_night = 1 if target_hour.hour < 6 or target_hour.hour >= 22 else 0

    async with async_session() as db:
        for key in keys:
            key = key.decode()
            parts = key.split(":")
            resident_id = int(parts[1])

            data = redis_client.hgetall(key)
            motion = int(data.get(b"motion_count", 0))
            door = int(data.get(b"door_count", 0))

            avg_interval = 60 / motion if motion > 0 else 0
            
            # 🔥 야간일 때만 야간 움직임으로 기록!
            night_motion = motion if is_night else 0

            # 🔥 현재 분(minute)을 정확히 기록
            first_motion = current_minute if motion > 0 else 0
            last_motion_min = current_minute if motion > 0 else 0

            # 🔥 x3 평균 간격과 x6 마지막 움직임을 완벽하게 갱신하는 쿼리
            await db.execute(text("""
                INSERT INTO hourly_features(
                    resident_id, target_hour, x1_motion_count, x2_door_count,
                    x3_avg_interval, x4_night_motion_count, x5_first_motion_min,
                    x6_last_motion_min, created_at, updated_at
                )
                VALUES(
                    :rid, :target_hour, :motion, :door, :avg_interval,
                    :night_motion, :first_motion, :last_motion_min, NOW(), NOW()
                )
                ON DUPLICATE KEY UPDATE
                    x1_motion_count = x1_motion_count + VALUES(x1_motion_count),
                    x2_door_count = x2_door_count + VALUES(x2_door_count),
                    x3_avg_interval = IF((x1_motion_count + VALUES(x1_motion_count)) > 0, 60.0 / (x1_motion_count + VALUES(x1_motion_count)), 0),
                    x4_night_motion_count = x4_night_motion_count + VALUES(x4_night_motion_count),
                    x6_last_motion_min = IF(VALUES(x1_motion_count) > 0, VALUES(x6_last_motion_min), x6_last_motion_min),
                    updated_at = NOW()
                """), {
                "rid": resident_id,
                "target_hour": target_hour,
                "motion": motion,
                "door": door,
                "avg_interval": avg_interval,
                "night_motion": night_motion,
                "first_motion": first_motion,
                "last_motion_min": last_motion_min
            })

            redis_client.delete(key)

        await db.commit()


# ------------------------
# detector 실행 (테스트용으로 1분마다 돌게 변경)
# ------------------------
async def run_detector():
    print("detector 실행 (개인 AI 모델 + 하이브리드 검증)")
    subprocess.run([sys.executable, "-m", "app.ml.detector_model"])


# ------------------------
# main worker
# ------------------------
async def main():
    print("🚀 integrated sensor worker start (Test Mode: 1 min cycle)")

    last_agg = None
    last_detector = None

    while True:
        now = datetime.now()

        # 센서 이벤트 생성 (매 loop)
        await generate_fake_sensor()

        # 💡 테스트를 위해 5분(300초) -> 1분(60초) 집계로 단축
        if last_agg is None or (now - last_agg).seconds >= 60:
            await aggregate_sensor()
            last_agg = now

        # 💡 테스트를 위해 1시간(3600초) -> 1분(60초) 마다 detector 실행
        if last_detector is None or (now - last_detector).seconds >= 300:
            await run_detector()
            last_detector = now

        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())