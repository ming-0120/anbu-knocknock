import time
from datetime import datetime, timedelta

import redis
from app.models import SensorEvent
from app.db.database import SessionLocal


redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True
)


def get_bucket_time(dt: datetime, window_minutes: int = 5):
    bucket_minute = (dt.minute // window_minutes) * window_minutes

    return dt.replace(
        minute=bucket_minute,
        second=0,
        microsecond=0
    )


def scan_keys(pattern: str):
    cursor = 0
    keys = []

    while True:
        cursor, batch = redis_client.scan(cursor, match=pattern, count=1000)
        keys.extend(batch)

        if cursor == 0:
            break

    return keys


def flush_previous_bucket_to_db():
    now = datetime.now()
    flush_time = now - timedelta(minutes=5)

    bucket_time = get_bucket_time(flush_time)

    bucket_str = bucket_time.strftime("%Y%m%d%H%M")

    search_pattern = f"sensor_bucket:*:*:{bucket_str}"

    keys = scan_keys(search_pattern)

    if not keys:
        return

    events_to_insert = []

    try:

        for key in keys:

            _, device_id, event_type, _ = key.split(":")

            val = redis_client.get(key)

            if val is None:
                continue

            total_count = int(float(val))

            events_to_insert.append(
                SensorEvent(
                    device_id=int(device_id),
                    event_type=event_type,
                    event_value=total_count,
                    event_at=bucket_time
                )
            )

        if not events_to_insert:
            return

        with SessionLocal() as db:

            db.add_all(events_to_insert)
            db.commit()

        # DB commit 성공 후에만 Redis 삭제
        redis_client.delete(*keys)

        print(
            f"[{now}] bucket({bucket_str}) "
            f"{len(events_to_insert)}건 DB 저장 완료"
        )

    except Exception as e:
        print(f"[ERROR] DB 저장 오류: {e}")


def wait_until_next_bucket(window_minutes=5):

    while True:

        now = datetime.now()

        if now.minute % window_minutes == 0 and now.second == 1:
            return

        time.sleep(0.5)


if __name__ == "__main__":

    print("센서 데이터 통합 저장 워커 시작...")

    while True:

        wait_until_next_bucket()

        flush_previous_bucket_to_db()

        time.sleep(2)