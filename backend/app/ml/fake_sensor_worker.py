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

# DB 및 Redis 설정
engine = create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

redis_client = redis.Redis(host="localhost", port=6379, db=0)


# ------------------------
# bucket 계산 (테스트용 1분 단위)
# ------------------------
def get_bucket():
    now = datetime.now()
    # 분 단위 버킷 생성
    bucket = now.replace(second=0, microsecond=0)
    return bucket.strftime("%Y%m%d%H%M")


# ------------------------
# fake sensor event (고위험군 5명 강제 생성 로직 포함)
# ------------------------
async def generate_fake_sensor():
    bucket = get_bucket()
    async with async_session() as db:
        result = await db.execute(text("SELECT resident_id FROM residents"))
        residents = result.fetchall()

    # 🔥 시연용 고위험군 ID 설정 (DB에 있는 실제 ID로 변경하세요)
    # 이 5명은 활동이 거의 없는 상태로 시뮬레이션됩니다.
    high_risk_ids = [164, 167, 204, 230, 260] 

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating sensor events...")

    for row in residents:
        rid = row[0]
        key = f"sensor:{rid}:{bucket}"
        
        # 1. 고위험군 시뮬레이션 (ID 1~5)
        if rid in high_risk_ids:
            # 활동이 거의 없음 (5% 확률로만 1회 움직임) -> 모델이 '위험'으로 판단 유도
            if random.random() < 0.05:
                redis_client.hincrby(key, "motion_count", 1)
            # 문 열림(외출)은 아예 없음 -> 고립 상태
        
        # 2. 정상군 시뮬레이션 (그 외 ID)
        else:
            rand_val = random.random()
            # 정상적인 활동 (70% 확률로 1~3회 움직임)
            if rand_val < 0.7:
                redis_client.hincrby(key, "motion_count", random.randint(1, 3))

            # 정상적인 외출 활동 (10% 확률로 문 열림)
            if rand_val < 0.1:
                redis_client.hincrby(key, "door_count", 1)

        # Redis 데이터 유지 시간 (10분)
        redis_client.expire(key, 600)


# ------------------------
# Redis → DB 집계 (Hourly Features 업데이트)
# ------------------------
async def aggregate_sensor():
    bucket = get_bucket()
    # 현재 버킷에 해당하는 모든 센서 키 조회
    keys = redis_client.keys(f"sensor:*:{bucket}")

    if not keys:
        print(f"No data in Redis for bucket: {bucket}")
        return

    print(f"Aggregating bucket: {bucket} (Keys: {len(keys)})")
    now_time = datetime.now()
    target_hour = now_time.replace(minute=0, second=0, microsecond=0)
    current_minute = now_time.minute

    # 야간 판별 (22시 ~ 06시)
    is_night = 1 if target_hour.hour < 6 or target_hour.hour >= 22 else 0

    async with async_session() as db:
        for key in keys:
            key = key.decode()
            parts = key.split(":")
            resident_id = int(parts[1])

            data = redis_client.hgetall(key)
            motion = int(data.get(b"motion_count", 0))
            door = int(data.get(b"door_count", 0))

            # 평균 간격 계산 (60분 기준)
            avg_interval = 60 / motion if motion > 0 else 0
            night_motion = motion if is_night else 0

            # 현재 분 기록
            first_motion = current_minute if motion > 0 else 0
            last_motion_min = current_minute if motion > 0 else 0

            # DB Upsert 쿼리
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

            # 집계 완료된 Redis 키 삭제
            redis_client.delete(key)

        await db.commit()


# ------------------------
# detector 실행 (모델 예측 로직 호출)
# ------------------------
async def run_detector():
    print("\n[DETECTOR] Running ML Model Analysis...")
    # detector_model.py를 서브프로세스로 실행
    subprocess.run([sys.executable, "-m", "app.ml.detector_model"])


# ------------------------
# Main Loop
# ------------------------
async def main():
    print("🚀 Integrated Sensor Worker Started (Demo Mode)")
    print("💡 Target High-Risk IDs: [1, 2, 3, 4, 5]")

    last_agg = None
    last_detector = None

    while True:
        now = datetime.now()

        # 1. 센서 이벤트 생성 (10초마다 가짜 데이터 주입)
        await generate_fake_sensor()

        # 2. 1분마다 Redis 데이터를 DB로 집계
        if last_agg is None or (now - last_agg).total_seconds() >= 60:
            await aggregate_sensor()
            last_agg = now

        # 3. 1분마다 Detector(모델) 실행하여 위험도 계산
        # 시연을 위해 실행 주기를 1분(60초)으로 대폭 단축함
        if last_detector is None or (now - last_detector).total_seconds() >= 60:
            await run_detector()
            last_detector = now

        # 루프 간격 (10초)
        await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")