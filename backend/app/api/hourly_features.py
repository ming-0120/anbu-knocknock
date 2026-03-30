from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.hourly_feature import HourlyFeature

router = APIRouter(prefix="/api/hourly-features", tags=["hourly-features"])
@router.get("/{resident_id}")
async def get_hourly_features(
    resident_id: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(HourlyFeature)
        .where(HourlyFeature.resident_id == resident_id)
        .order_by(HourlyFeature.target_hour.desc())
        .limit(24)
    )

    result = db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "hour": r.target_hour,
            "motion": r.x1_motion_count
        }
        for r in rows[::-1]
    ]