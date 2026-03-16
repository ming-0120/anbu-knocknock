from datetime import datetime, timezone, timedelta
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.dashboard import (
    HighRiskReq, HighRiskResp,
    MapSummaryReq, MapSummaryResp,
    GuResidentsReq, GuResidentsResp,
)
from app.repositories import dashboard_repository as repo
from app.utils.cache import make_cache_key, cached_with_lock
from app.core.config import get_settings

settings = get_settings()

async def get_high_risk(body: HighRiskReq, db: AsyncSession, redis) -> HighRiskResp:
    payload = body.model_dump()
    key = make_cache_key("dashboard:high-risk", payload)
    stale_key = make_cache_key("dashboard:high-risk:stale", payload)

    async def loader():
        now = datetime.now(timezone.utc)
        since = now - timedelta(minutes=body.window_minutes)
        effective_min_level = body.min_level or "alert"
        rows = await repo.query_high_risk(db, since, body.limit, effective_min_level)
    
        for r in rows:
            if isinstance(r.get("reason_codes"), str):
                try:
                    r["reason_codes"] = json.loads(r["reason_codes"])
                except Exception:
                    r["reason_codes"] = None
    
        return {
            "window_minutes": body.window_minutes,
            "generated_at": now,
            "items": rows
        }

    data = await cached_with_lock(
        redis=redis,
        key=key,
        ttl_seconds=settings.DASH_HIGH_RISK_TTL,
        stale_key=stale_key,
        loader=loader,
    )
    return data

async def get_map_summary(body, db):
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=body.window_minutes)

    rows = await repo.query_map_summary(db, since, body.min_level)

    return {"items": rows}

async def get_gu_residents(body, db):
    rows = await repo.query_gu_residents(
        db,
        body.gu,
        body.limit,
        body.include_latest_score,
    )
    return {
        "gu": body.gu,
        "items": rows,
    }