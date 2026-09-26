"""
Single Redis connection pool, reused for both of Redis's two jobs in this
system (§2.4): the /api/stats read-through cache and the distributed
rate limiter. It is one piece of infrastructure serving two purposes --
that's deliberate, not laziness.
"""
import redis.asyncio as redis

from ...config import get_settings

_settings = get_settings()
redis_client = redis.from_url(_settings.redis_url, decode_responses=True)


async def close_redis():
    await redis_client.aclose()
