import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_client = None
_memory_rate_limit: dict[str, list[float]] = defaultdict(list)


async def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable, using in-memory fallback: %s", exc)
        return None


async def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Returns True if request is allowed."""
    redis = await get_redis()
    now = datetime.now(timezone.utc).timestamp()

    if redis:
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        return int(results[0]) <= limit

    bucket = _memory_rate_limit[key]
    bucket[:] = [t for t in bucket if now - t < window_seconds]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


async def blacklist_refresh_token(jti_hash: str, expires_at: datetime) -> None:
    redis = await get_redis()
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl <= 0:
        return
    if redis:
        await redis.setex(f"refresh_blacklist:{jti_hash}", ttl, "1")
        return
    _memory_rate_limit[f"bl:{jti_hash}"].append(now_ts := datetime.now(timezone.utc).timestamp())


async def is_refresh_token_blacklisted(jti_hash: str) -> bool:
    redis = await get_redis()
    if redis:
        return await redis.exists(f"refresh_blacklist:{jti_hash}") > 0
    return f"bl:{jti_hash}" in _memory_rate_limit
