import logging
from datetime import datetime
import redis.asyncio as Redis
from redis.exceptions import RedisError
from fastapi import HTTPException

logger = logging.getLogger(__name__)

async def buffer_sensor_event(
    redis_client: Redis.Redis,
    device_uid: str,
    event_type: str,
    event_value: float,
    event_at: datetime
) -> str:
    """
    센서 이벤트를 1분 단위 타임 버킷으로 Redis에 누적(합산)합니다.
    """
    # 1. 분 단위 버킷 생성을 위한 시간 포맷팅
    minute_str = event_at.strftime("%Y%m%d%H%M")
    
    # 2. Redis Key 생성
    bucket_key = f"sensor_bucket:{device_uid}:{event_type}:{minute_str}"
    increment_value = event_value if event_value is not None else 1.0
    
    try:
        # 3. Redis 파이프라인으로 원자적 연산 (합산 및 5분 뒤 삭제 예약)
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.incrbyfloat(bucket_key, increment_value)
            pipe.expire(bucket_key, 300) 
            await pipe.execute()
            
        return bucket_key
        
    except RedisError as e:
        logger.exception("Redis error during time bucketing. err=%s", str(e))
        raise HTTPException(status_code=500, detail="Internal Redis Error")