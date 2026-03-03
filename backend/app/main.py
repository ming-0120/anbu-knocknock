from fastapi import FastAPI
from app.api.routes import health, sensor_events, ingest
from app.db.database import engine
from sqlalchemy import text
from app.db.base import Base  # 이 import가 모델 로드를 보장
import os
from contextlib import asynccontextmanager
from app.api.routes.sensor_events import router as sensor_events_router
import redis.asyncio as redis

Base.metadata.create_all(bind=engine)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    app.state.redis = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )
    try:
        await app.state.redis.ping()
        yield
    finally:
        # shutdown
        await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)

app.include_router(health.router)
app.include_router(sensor_events.router, prefix="/sensor-events")
app.include_router(ingest.router)
