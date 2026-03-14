import json
import hashlib
from typing import Any, Optional, Callable, Awaitable
from datetime import date, datetime

def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return str(o)  # Decimal 등도 안전하게 문자열로

def _stable_json_dumps(obj):
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )

def make_cache_key(prefix: str, payload: dict) -> str:
    raw = _stable_json_dumps(payload)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{prefix}:{h}"

async def cache_get_json(redis, key: str) -> Optional[Any]:
    v = await redis.get(key)
    if not v:
        return None
    return json.loads(v)

async def cache_set_json(redis, key: str, value: Any, ttl_seconds: int) -> None:
    await redis.set(key, _stable_json_dumps(value), ex=ttl_seconds)

async def cached_with_lock(
    redis,
    key: str,
    ttl_seconds: int,
    loader: Callable[[], Awaitable[Any]],
    lock_ttl_seconds: int = 8,
    stale_key: Optional[str] = None,
) -> Any:
    hit = await cache_get_json(redis, key)
    if hit is not None:
        return hit

    lock_key = f"{key}:lock"
    got_lock = await redis.set(lock_key, "1", nx=True, ex=lock_ttl_seconds)

    if not got_lock:
        if stale_key:
            stale = await cache_get_json(redis, stale_key)
            if stale is not None:
                return stale
        hit2 = await cache_get_json(redis, key)
        if hit2 is not None:
            return hit2
        data = await loader()
        await cache_set_json(redis, key, data, ttl_seconds)
        return data

    try:
        data = await loader()
        await cache_set_json(redis, key, data, ttl_seconds)
        if stale_key:
            await cache_set_json(redis, stale_key, data, ttl_seconds * 5)
        return data
    finally:
        await redis.delete(lock_key)