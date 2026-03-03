from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

import redis.asyncio as Redis
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.deps.redis import get_redis
# 👉 1. 방금 만든 창고 관리자(서비스) 함수를 불러옵니다!
from app.services.sensor_service import buffer_sensor_event

logger = logging.getLogger(__name__)
router = APIRouter()

EventType = Literal["door_open", "door_close", "motion"]

class SensorEventIn(BaseModel):
    device_uid: str = Field(..., min_length=5)
    event_type: EventType
    event_value: Optional[float] = 1.0
    event_at: Optional[datetime] = None

def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_sensor_event(
    payload: SensorEventIn,
    redis_client: Redis.Redis = Depends(get_redis),
):
    # 시간 기준점 설정 (UTC)
    event_at = _as_utc(payload.event_at) if payload.event_at else datetime.now(timezone.utc)
    
    # 👉 2. 문지기가 창고 관리자를 호출해서 일을 시킵니다.
    bucket_key = await buffer_sensor_event(
        redis_client=redis_client,
        device_uid=payload.device_uid,
        event_type=payload.event_type,
        event_value=payload.event_value,
        event_at=event_at
    )

    # 3. 작업이 끝났으니 센서에게 응답을 보냅니다.
    return {
        "status": "success", 
        "message": "Event buffered in Redis",
        "bucket_key": bucket_key
    }