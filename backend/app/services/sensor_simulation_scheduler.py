import asyncio
import random
import logging
import aiohttp
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models.device import Device

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 설정값
API_URL = "http://localhost:8000/sensor-events/"  # FastAPI 서버 주소
CONCURRENT_REQUESTS = 50  # 한 번에 쏘는 비동기 요청 수 (조절 가능)

async def fetch_all_devices():
    """DB에서 모든 기기의 UID와 타입을 가져옵니다."""
    async with AsyncSessionLocal() as session:
        stmt = select(Device.device_uid, Device.device_type)
        result = await session.execute(stmt)
        return [{"uid": r[0], "type": r[1]} for r in result.all()]

async def send_sensor_data(session, device):
    """실제 API로 데이터를 전송하는 함수"""
    # 이벤트 타입 결정
    if device['type'] == 'door':
        event_type = random.choice(["door_open", "door_close"])
    else:
        event_type = "motion"

    payload = {
        "device_uid": device['uid'],
        "event_type": event_type,
        "event_value": 1.0,
        "event_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        async with session.post(API_URL, json=payload, timeout=2) as response:
            return response.status == 201
    except Exception:
        return False

async def run_simulation_round(devices):
    """1분 단위의 시뮬레이션 한 회차 실행"""
    # 전체 1만 대 중 5~10%만 활동한다고 가정 (현실적인 수치)
    active_ratio = random.uniform(0.05, 0.10)
    active_count = int(len(devices) * active_ratio)
    active_devices = random.sample(devices, active_count)
    
    logger.info(f"🚀 시뮬레이션 시작: {len(devices)}대 중 {active_count}대 활동 발생")

    async with aiohttp.ClientSession() as session:
        tasks = []
        for device in active_devices:
            tasks.append(send_sensor_data(session, device))
            
            # 너무 한꺼번에 쏘지 않도록 세마포어(제한) 역할
            if len(tasks) >= CONCURRENT_REQUESTS:
                await asyncio.gather(*tasks)
                tasks = []
        
        if tasks:
            await asyncio.gather(*tasks)

    logger.info(f"✅ {active_count}건의 데이터 전송 완료 (Redis 누적 중)")

async def main_scheduler():
    print("=========================================")
    print("📡 고독사 예방 시스템 가상 데이터 스케줄러")
    print("=========================================\n")

    # 1. 초기 기기 로드
    devices = await fetch_all_devices()
    if not devices:
        logger.error("🚨 DB에 기기가 없습니다. finalize_devices 스크립트를 먼저 실행하세요.")
        return

    while True:
        now = datetime.now()
        
        # 2. 매 분 0초가 되면 데이터 발송 시작
        if now.second == 0:
            start_time = time.time()
            await run_simulation_round(devices)
            
            # 1시간마다 기기 목록 새로고침 (혹시 추가될 수 있으니)
            if now.minute == 0:
                devices = await fetch_all_devices()
            
            # 중복 실행 방지를 위해 충분히 쉬기
            await asyncio.sleep(50)
        
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    import time
    try:
        asyncio.run(main_scheduler())
    except KeyboardInterrupt:
        print("\n🛑 시뮬레이터를 종료합니다.")