# app/services/hourly_aggregator.py
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, delete, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor_event import SensorEvent
from app.models.device import Device
from app.models.hourly_feature import HourlyFeature


async def aggregate_hourly_features(db: AsyncSession, target_hour: datetime) -> int:
    """
    target_hour(정각) ~ target_hour+1h 구간을 resident별로 집계해 hourly_features에 적재
    - x1_motion_count: motion 이벤트 수
    - x2_door_count: door_close 이벤트 수
    - x6_last_motion_min: 구간 끝 시각 기준 마지막 motion 이후 경과 분 (motion 없으면 60)
    """
    start_dt = target_hour.replace(minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=1)

    stmt = (
        select(
            Device.resident_id.label("resident_id"),
            func.sum(case((SensorEvent.event_type == "motion", 1), else_=0)).label("x1"),
            func.sum(case((SensorEvent.event_type == "door_close", 1), else_=0)).label("x2"),
            func.max(case((SensorEvent.event_type == "motion", SensorEvent.event_at), else_=None)).label("last_motion_at"),
        )
        .select_from(SensorEvent)
        .join(Device, SensorEvent.device_id == Device.device_id)
        .where(and_(SensorEvent.event_at >= start_dt, SensorEvent.event_at < end_dt))
        .group_by(Device.resident_id)
    )

    rows = (await db.execute(stmt)).all()
    if not rows:
        return 0

    # 해당 시간 블록 재생성(테스트용): target_hour 기준 삭제 후 삽입
    await db.execute(delete(HourlyFeature).where(HourlyFeature.target_hour == start_dt))

    payload = []
    for r in rows:
        last_motion_at = r.last_motion_at
        if last_motion_at is None:
            x6 = 60
        else:
            x6 = int((end_dt - last_motion_at).total_seconds() // 60)
            x6 = max(0, min(1440, x6))

        payload.append(
            HourlyFeature(
                resident_id=int(r.resident_id),
                target_hour=start_dt,
                x1_motion_count=int(r.x1 or 0),
                x2_door_count=int(r.x2 or 0),
                x6_last_motion_min=int(x6),
            )
        )

    db.add_all(payload)
    await db.flush()
    return len(payload)