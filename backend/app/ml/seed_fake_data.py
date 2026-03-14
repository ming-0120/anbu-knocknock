# seed_fake_data.py
import asyncio
import random
import hashlib
from datetime import datetime, timedelta

from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def seed_data():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT resident_id FROM residents"))
        residents = [row[0] for row in result.fetchall()]

        if not residents:
            print("거주자 데이터가 없습니다.")
            return

        print(f"총 {len(residents)}명의 30일 치 과거 데이터를 생성합니다. 잠시만 기다려주세요...")
        
        # 💡 기존 임시 데이터 삭제 (깔끔한 초기화)
        await db.execute(text("TRUNCATE TABLE hourly_features"))
        
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        current_time = now - timedelta(days=30)
        total_inserted = 0
        
        while current_time <= now:
            hour = current_time.hour
            hour_str = current_time.strftime("%Y%m%d_%H")
            
            for rid in residents:
                seed_string = f"{rid}_{hour_str}"
                hash_val = int(hashlib.md5(seed_string.encode()).hexdigest(), 16)
                rand_val = (hash_val % 1000) / 1000.0
                
                # AI 학습을 위한 현실적인 패턴 (정상 85%)
                if rand_val < 0.05:
                    motion = 0; door = 0
                elif rand_val < 0.15:
                    motion = 0 if (23 <= hour or hour <= 5) else random.randint(1, 2)
                    door = 0 if random.random() < 0.9 else 1
                else:
                    motion = random.randint(0, 1) if (23 <= hour or hour <= 5) else random.randint(5, 12)
                    door = 1 if random.random() < 0.05 else 0

                avg_interval = 60 / motion if motion > 0 else 0
                night_motion = motion if hour <= 5 else 0
                first_motion = random.randint(0, 120) if motion > 0 else 0
                last_motion_min = 5 if motion > 0 else 60

                await db.execute(text("""
                    INSERT INTO hourly_features(
                        resident_id, target_hour, x1_motion_count, x2_door_count, 
                        x3_avg_interval, x4_night_motion_count, x5_first_motion_min, 
                        x6_last_motion_min, created_at, updated_at
                    ) VALUES (
                        :rid, :target_hour, :motion, :door, 
                        :avg_interval, :night_motion, :first_motion, :last_motion_min, 
                        NOW(), NOW()
                    )
                """), {
                    "rid": rid, "target_hour": current_time, "motion": motion, "door": door,
                    "avg_interval": avg_interval, "night_motion": night_motion,
                    "first_motion": first_motion, "last_motion_min": last_motion_min
                })
                total_inserted += 1
            
            current_time += timedelta(hours=1)
        
        await db.commit()
        print(f"완료! 총 {total_inserted}건의 과거 데이터가 성공적으로 생성되었습니다.")

if __name__ == "__main__":
    asyncio.run(seed_data())