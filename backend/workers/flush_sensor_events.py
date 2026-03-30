import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import redis.asyncio as Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal
from app.models.sensor_event import SensorEvent
from app.models.device import Device
from app.core.config import settings # 환경변수 불러오기 위해 추가

# 워커용 로거 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def flush_previous_minute_data(redis_client: Redis.Redis) -> None:
    now = datetime.now(timezone.utc)
    prev_minute_dt = now - timedelta(minutes=1)
    target_minute_str = prev_minute_dt.strftime("%Y%m%d%H%M")
    
    logger.info(f"DB Flush 시작: 대상 시간 버킷 [{target_minute_str}]")

    search_pattern = f"sensor_bucket:*:*:{target_minute_str}"
    
    keys = []
    async for key in redis_client.scan_iter(match=search_pattern):
        keys.append(key)
        
    if not keys:
        logger.info("저장할 누적 데이터가 없습니다.")
        return

    events_to_insert: List[dict] = [] # 딕셔너리로 타입 힌트 변경
    device_uids_to_update = set()

    try:
        async with AsyncSessionLocal() as session:
            for key in keys:
                if isinstance(key, bytes):
                    key_str = key.decode("utf-8")
                else:
                    key_str = key
                    
                parts = key_str.split(":")
                device_uid = parts[1]
                event_type = parts[2]
                
                total_value = await redis_client.get(key)
                if not total_value:
                    continue
                    
                device_uids_to_update.add(device_uid)

                bucket_time = prev_minute_dt.replace(second=0, microsecond=0)
                
                events_to_insert.append({
                    "device_uid": device_uid,
                    "event_type": event_type,
                    "event_value": float(total_value),
                    "event_at": bucket_time,
                    "redis_key": key_str
                })

            if not events_to_insert:
                return

            stmt = select(Device).where(Device.device_uid.in_(device_uids_to_update))
            result = await session.execute(stmt)
            devices = result.scalars().all()
            
            device_map = {device.device_uid: device for device in devices}
            
            db_instances = []
            keys_to_delete = []
            
            for item in events_to_insert:
                device = device_map.get(item["device_uid"])
                if device:
                    db_instances.append(
                        SensorEvent(
                            device_id=device.device_id,
                            event_type=item["event_type"],
                            event_value=item["event_value"],
                            event_at=item["event_at"]
                        )
                    )
                    device.last_seen_at = now
                    keys_to_delete.append(item["redis_key"])
                else:
                    logger.warning(f"등록되지 않은 기기 제외: {item['device_uid']}")

            if db_instances:
                session.add_all(db_instances)
                await session.commit()
                logger.info(f"DB 저장 성공: 이벤트 {len(db_instances)}건, 기기 업데이트 {len(device_map)}대")
                
                if keys_to_delete:
                    await redis_client.delete(*keys_to_delete)
                    logger.debug(f"정리된 Redis 키: {len(keys_to_delete)}건")

    except Exception as e:
        logger.error(f"DB Flush 중 에러 발생: {e}", exc_info=True)


async def main_worker_loop():
    logger.info("센서 데이터 DB 저장 워커 시작 (1분 주기)")
    
    # 수정 포인트: 제너레이터 대신 Redis 클라이언트를 직접 생성합니다.
    # settings 파일에 정의된 Redis 연결 정보를 사용합니다.
    redis_client = Redis.Redis(
        host=settings.REDIS_HOST, # 환경변수에 맞게 수정하세요 (예: "localhost")
        port=settings.REDIS_PORT, # 예: 6379
        db=settings.REDIS_DB,     # 예: 0
        decode_responses=True
    )
    
    try:
        while True:
            now_sec = datetime.now().second
            if now_sec in (1, 2): 
                await flush_previous_minute_data(redis_client)
                await asyncio.sleep(55) 
            
            await asyncio.sleep(0.5) 
            
    except asyncio.CancelledError:
        logger.info("워커 프로세스가 종료 요청을 받았습니다.")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main_worker_loop())
    except KeyboardInterrupt:
        logger.info("사용자에 의해 워커가 정지되었습니다.")