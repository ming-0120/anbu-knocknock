from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.database import get_async_db

router = APIRouter()

@router.post("/simulate/anomaly")
async def simulate_anomaly(
    resident_id: int = 164,
    db: AsyncSession = Depends(get_async_db)
):
    await db.execute(text("""
    INSERT INTO risk_scores (
        resident_id, feature_id, score, level, s_base, scored_at
    )
    VALUES (
        :rid,
        (
            SELECT feature_id FROM hourly_features
            WHERE resident_id = :rid
            ORDER BY created_at DESC
            LIMIT 1
        ),
        0.95,
        'emergency',
        0.5,
        NOW()
    )
    ON DUPLICATE KEY UPDATE
        score = VALUES(score),
        level = VALUES(level),
        s_base = VALUES(s_base),
        scored_at = NOW()
"""), {"rid": resident_id})
    await db.commit()

    return {"status": "ok", "resident_id": resident_id}