import time
from datetime import datetime, timedelta
import redis
from sqlalchemy.orm import sessionmaker
from app.models import SensorEvent
from app.db.database import SessionLocal 

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def flush_previous_minute_to_db():
    db = SessionLocal()
    
    # 1. '직전 분'의 시간 문자열 계산 (현재 08:18 이면 08:17 계산)
    now = datetime.now()
    prev_minute_dt = now - timedelta(minutes=1)
    prev_minute_str = prev_minute_dt.strftime("%Y%m%d%H%M")
    
    # 2. Redis에서 직전 분에 해당하는 모든 키 검색
    search_pattern = f"sensor_bucket:*:*:{prev_minute_str}"
    keys = redis_client.keys(search_pattern)
    
    if not keys:
        return # 저장할 데이터가 없으면 종료
        
    events_to_insert = []
    
    try:
        # 3. 찾은 키들의 값을 읽어서 DB 모델로 변환
        for key in keys:
            # key 예시: "sensor_bucket:12:motion:202603030817"
            _, device_id, event_type, _ = key.split(":")
            
            # 누적된 호출 횟수(합산 값) 가져오기
            total_count = float(redis_client.get(key))
            
            # DB 이벤트 객체 생성 (event_value에 합산 횟수 기록)
            events_to_insert.append(
                SensorEvent(
                    device_id=int(device_id),
                    event_type=event_type,
                    event_value=total_count, 
                    event_at=prev_minute_dt.replace(second=0, microsecond=0) # 해당 분의 정각으로 기록
                )
            )
            
        # 4. DB에 한 번에 Bulk Insert (100번의 API 호출이 1번의 DB Insert로 압축됨)
        db.add_all(events_to_insert)
        db.commit()
        
        # 5. DB 저장 완료 후 Redis에서 키 삭제 (메모리 정리)
        redis_client.delete(*keys)
        
        print(f"[{now}] 이전 분({prev_minute_str}) 데이터 {len(events_to_insert)}건 DB 통합 저장 완료.")
        
    except Exception as e:
        print(f"DB 저장 오류: {e}")
        db.rollback()
    finally:
        db.close()

# 실제 운영 시에는 APScheduler나 Celery Beat, 혹은 단순 while 루프로 1분마다 실행
if __name__ == "__main__":
    print("센서 데이터 통합 저장 워커 시작...")
    while True:
        # 매 정각(0초) 부근에 실행되도록 대기 (간단한 구현)
        current_second = datetime.now().second
        if current_second == 1: # 매 분 1초에 실행
            flush_previous_minute_to_db()
            time.sleep(50) # 중복 실행 방지
        time.sleep(0.5)