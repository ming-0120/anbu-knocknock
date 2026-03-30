import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from app.db.database import AsyncSessionLocal
from app.models.resident import Resident
from app.models.device import Device
from app.models.resident_setting import ResidentSetting

async def finalize_devices():
    print("🛠️ 기기 1만 대 등록 로직을 시작합니다...")
    
    async with AsyncSessionLocal() as session:
        # 1. 모든 입주민 목록 가져오기
        result = await session.execute(select(Resident))
        all_residents = result.scalars().all()
        total_residents = len(all_residents)
        print(f"📊 현재 등록된 입주민: {total_residents}명")

        new_devices = []
        new_settings = []
        
        print("🔗 입주민별 기기 매핑 및 설정 생성 중...")
        for idx, resident in enumerate(all_residents):
            # 해당 주민에게 이미 기기가 있는지 확인 (중복 방지)
            device_check = await session.execute(
                select(func.count(Device.device_id)).where(Device.resident_id == resident.resident_id)
            )
            if device_check.scalar() >= 2:
                continue # 이미 3대 이상 있으면 패스

            # 8자리 랜덤 접두어로 겹치지 않는 UID 생성
            uid_prefix = str(uuid.uuid4())[:8].upper()
            
            # 기기 3대 (현관 DOR, 거실 MOT-L, 침실 MOT-B) 생성
            new_devices.append(Device(
                resident_id=resident.resident_id,
                device_uid=f"DOR-{uid_prefix}-{resident.resident_id}",
                device_type="door",
                location_label="현관",
                status="active",
                firmware_version="v1.0.0",
                created_at=datetime.now(timezone.utc)
            ))
            new_devices.append(Device(
                resident_id=resident.resident_id,
                device_uid=f"MOT-L-{uid_prefix}-{resident.resident_id}",
                device_type="motion",
                location_label="거실",
                status="active",
                firmware_version="v1.0.0",
                created_at=datetime.now(timezone.utc)
            ))
            # ResidentSetting 테이블도 비어있다면 생성 (이미지 컬럼 기반)
            setting_check = await session.execute(
                select(func.count(ResidentSetting.resident_id)).where(ResidentSetting.resident_id == resident.resident_id)
            )
            if setting_check.scalar() == 0:
                new_settings.append(ResidentSetting(
                    resident_id=resident.resident_id,
                    sensitivity_weight=1.0,
                    alpha_factor=0.5,
                    no_activity_threshold_min=720, # 12시간
                    emergency_sms_enabled=1
                ))

            # 메모리 관리를 위해 200명 단위로 중간 저장
            if len(new_devices) >= 600:
                session.add_all(new_devices)
                session.add_all(new_settings)
                await session.commit()
                new_devices, new_settings = [], []
                print(f"📦 처리 중... ({idx+1}/{total_residents})")

        # 남은 데이터 저장
        if new_devices:
            session.add_all(new_devices)
            session.add_all(new_settings)
            await session.commit()

        # 최종 개수 확인
        final_device_count = await session.execute(select(func.count(Device.device_id)))
        print(f"\n✅ 작업 완료! 현재 총 기기 수: {final_device_count.scalar()}대")

if __name__ == "__main__":
    asyncio.run(finalize_devices())