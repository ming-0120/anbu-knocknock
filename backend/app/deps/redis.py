from typing import Optional
import redis.asyncio as redis

_redis: Optional[redis.Redis] = None

def init_redis(host: str, port: int, db: int) -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
    return _redis

def get_redis() -> redis.Redis:
    if _redis is None:
        raise RuntimeError("Redis is not initialized")
    return _redis