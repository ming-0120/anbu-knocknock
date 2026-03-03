import redis
import json
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from app.schemas.sensor_event import SensorEventIn

router = APIRouter()

# 🌟 Redis 클라이언트 연결 세팅 (기본 로컬 6379 포트)
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@router.post("/sensor-events")
def ingest_sensor_event(body: SensorEventIn):
    try:
        # 1. Pydantic 모델(body)을 딕셔너리로 변환 (datetime 객체도 안전하게 문자열로 변환됨)
        event_data = jsonable_encoder(body)
        
        # 2. Redis의 'sensor_events_queue'라는 이름의 대기열 리스트(왼쪽)에 JSON으로 묶어 밀어넣기
        redis_client.lpush("sensor_events_queue", json.dumps(event_data))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis 저장 실패: {str(e)}")

    # DB 저장을 기다리지 않고 바로 응답을 뱉으므로 속도가 미친듯이 빠릅니다!
    return {"ok": True, "message": "Queued in Redis"}