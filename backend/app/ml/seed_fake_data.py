import asyncio
import random
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def seed_data():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT resident_id FROM residents ORDER BY resident_id"))
        residents = [row[0] for row in result.fetchall()]

        if not residents:
            print("거주자 데이터가 없습니다.")
            return

        # 1. 고정 비율에 따른 그룹 배정 (민경님 설계 반영)
        total_count = len(residents)
        emergency_ids = set(residents[:int(total_count * 0.03)]) # 상위 3%
        alert_ids = set(residents[int(total_count * 0.03):int(total_count * 0.10)]) # 다음 7%
        watch_ids = set(residents[int(total_count * 0.10):int(total_count * 0.25)]) # 다음 15%
        
        print(f"규모: 총 {total_count}명 (고위험: {len(emergency_ids)}, 경고: {len(alert_ids)}, 주의: {len(watch_ids)})")
        
        await db.execute(text("SET SQL_SAFE_UPDATES = 0"))
        await db.execute(text("TRUNCATE TABLE hourly_features"))
        
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        start_date = now - timedelta(days=30)
        current_time = start_date
        total_inserted = 0
        
        print("30일 치 데이터를 생성 중입니다...")

        while current_time <= now:
            hour = current_time.hour
            is_night = (23 <= hour or hour <= 5)
            # 마지막 2일(48시간)을 사고 발생 구간으로 설정
            is_accident_period = (current_time > now - timedelta(days=2))
            
            for rid in residents:
                # 기본 정상 패턴 (08시 기상, 22시 취침 스타일)
                motion = random.randint(8, 15) if not is_night else random.randint(0, 1)
                door = 1 if (hour == 8 or hour == 18) and random.random() < 0.7 else 0
                
                # 💡 사고 주입 로직
                if is_accident_period:
                    if rid in emergency_ids:
                        motion = 0; door = 0 # 완전 중단 (사망/실신 의심)
                    elif rid in alert_ids:
                        motion = int(motion * 0.2); door = 0 # 80% 감소 (거동 불가)
                    elif rid in watch_ids:
                        motion = int(motion * 0.5) # 50% 감소 (이상 징후)

                # 파라미터 계산
                avg_interval = 60 / motion if motion > 0 else 0
                night_motion = motion if is_night else 0
                first_motion = random.randint(0, 20) if motion > 0 else 0
                last_motion_min = random.randint(40, 59) if motion > 0 else 0

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
        print(f"✅ 완료! 총 {total_inserted}건의 실무형 데이터가 생성되었습니다.")

if __name__ == "__main__":
    asyncio.run(seed_data())