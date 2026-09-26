"""
Distributed rate limiter, Job 2 of Redis's two jobs (§2.4).

Why Redis and not an in-process dict: the moment the HPA scales the backend
to N pods, an in-process counter would allow N times the intended traffic,
because each pod has its own counter. Redis is shared state, so the limit
is enforced across the whole fleet.

Algorithm: fixed window, one key per (client_ip, minute-bucket). INCR is
atomic in Redis, so concurrent requests never race each other for the count.
"""
import time
from dataclasses import dataclass

from .redis_client import redis_client
from ...config import get_settings


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int  # seconds, only meaningful when allowed is False


async def check_rate_limit(client_ip: str) -> RateLimitResult:
    settings = get_settings()
    window = int(time.time() // 60)
    key = f"ratelimit:{client_ip}:{window}"

    count = await redis_client.incr(key)
    if count == 1:
        # first request in this window sets the expiry; avoids a key that
        # lives forever if it's never touched again
        await redis_client.expire(key, 60)

    if count > settings.rate_limit_per_minute:
        ttl = await redis_client.ttl(key)
        return RateLimitResult(allowed=False, retry_after=max(ttl, 1))

    return RateLimitResult(allowed=True, retry_after=0)
