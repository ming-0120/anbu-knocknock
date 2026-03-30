from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager
from app.api.router import api_router
from app.core.config import get_settings
from app.deps.redis import init_redis
from app.websocket.router import router as websocket_router
import app.models
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    r = init_redis(settings.REDIS_HOST, settings.REDIS_PORT, settings.REDIS_DB)
    try:
        await r.ping()
        yield
    finally:
        await r.aclose()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(api_router)
    app.include_router(websocket_router)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    app.mount("/recordings", StaticFiles(directory="recordings"), name="recordings")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],   # ✅ OPTIONS 포함
        allow_headers=["*"],
    )
    return app

app = create_app()