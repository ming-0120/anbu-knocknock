import asyncio
import random
import uuid
from datetime import datetime, timezone
from faker import Faker
from sqlalchemy import select, func

from app.db.database import AsyncSessionLocal
from app.models.resident import Resident
from app.models.device import Device
from app.models.resident_setting import ResidentSetting

fake = Faker('ko_KR')

# 서울의 구 목록
SEOUL_GU_LIST = [
    "관악구", "동작구", "마포구", "서초구", "강남구", "송파구", 
    "은평구", "서대문구", "용산구", "성동구", "광진구", "동대문구", 
    "중랑구", "성북구", "강북구", "도봉구", "노원구", "양천구", 
    "강서구", "구로구", "금천구", "영등포구", "강동구", "종로구", "중구"
]

def generate_fake_reg_no():
    year = random.randint(30, 65)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    gender_code = random.choice([1, 2])
    # 형식: 550625-1 (8자리)
    return f"{year:02d}{month:02d}{day:02d}-{gender_code}"

async def seed_data():
    print("🌱 서울 지역 한정 시드 데이터 생성을 시작합니다...")
    
    async with AsyncSessionLocal() as session:
        # 1. 입주민 생성 (서울 주소 적용)
        stmt = select(func.count(Resident.resident_id))
        result = await session.execute(stmt)
        current_count = result.scalar()
        
        residents_to_create = 5000 - current_count
        
        if residents_to_create > 0:
            print(f"👨‍🦳 {residents_to_create}명의 서울 거주 입주민을 생성합니다...")
            for i in range(residents_to_create):
                seoul_gu = random.choice(SEOUL_GU_LIST)
                new_resident = Resident(
                    name=fake.name(),
                    resident_reg_no=generate_fake_reg_no(),
                    phone=f"010-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
                    # '서울특별시 구이름 가짜도로명' 형식으로 생성
                    address_main=f"서울특별시 {seoul_gu} {fake.street_name()} {random.randint(1, 100)}길",
                    zip_code=fake.postcode(),
                    address_detail=f"{random.randint(1, 15)}동 {random.randint(101, 1500)}호",
                    lat=random.uniform(37.4, 37.7), # 서울 위도 범위
                    lon=random.uniform(126.8, 127.1), # 서울 경도 범위
                    created_at=datetime.now(timezone.utc)
                )
                session.add(new_resident)
                if i % 500 == 0:
                    await session.commit()
            await session.commit()
            print("✅ 서울 지역 입주민 생성 완료!")

        # 2. 기기 및 세팅 매핑 (이후 로직은 동일)
        print("🏠 기기 및 환경설정 매핑을 시작합니다...")
        result = await session.execute(select(Resident).where(Resident.resident_id > current_count))
        new_residents = result.scalars().all()
        
        for idx, resident in enumerate(new_residents):
            uid_prefix = str(uuid.uuid4())[:4].upper()
            
            # 가구당 3대 (도어1, 거실1, 침실1)
            devices = [
                Device(resident_id=resident.resident_id, device_uid=f"DOR-{uid_prefix}-{resident.resident_id}", 
                       device_type="door", location="현관", status="active"),
                Device(resident_id=resident.resident_id, device_uid=f"MOT-L-{uid_prefix}-{resident.resident_id}", 
                       device_type="motion", location="거실", status="active"),
                Device(resident_id=resident.resident_id, device_uid=f"MOT-B-{uid_prefix}-{resident.resident_id}", 
                       device_type="motion", location="침실", status="active")
            ]
            
            risk = random.choices(["정상", "주의", "위험"], weights=[80, 15, 5])[0]
            setting = ResidentSetting(resident_id=resident.resident_id, risk_level=risk)
            
            session.add_all(devices)
            session.add(setting)
            
            if idx % 200 == 0:
                await session.commit()
        
        await session.commit()
        print("🎉 모든 데이터 구축 완료!")

if __name__ == "__main__":
    asyncio.run(seed_data())