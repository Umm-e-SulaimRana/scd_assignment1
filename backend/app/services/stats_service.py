"""
Read-through cache for GET /api/stats (§2.4 Job 1). TTL as a safety net,
explicit invalidation on write as the primary mechanism -- the write path
(complaint_service.py) deletes this key the moment a complaint is created,
so the dashboard reflects new data immediately. The TTL alone would allow
up to 30s of staleness; invalidation alone would miss any writer that
forgets to invalidate (e.g. a future bulk-import script) -- together they
cover both failure modes.
"""
import json

from ..providers.cache.redis_client import redis_client
from ..repositories.complaint_repository import ComplaintRepository
from ..config import get_settings

STATS_CACHE_KEY = "stats:aggregate"


class StatsService:
    def __init__(self, repo: ComplaintRepository):
        self.repo = repo

    async def get_stats(self) -> tuple[dict, bool]:
        """Returns (stats, cache_hit)."""
        cached = await redis_client.get(STATS_CACHE_KEY)
        if cached:
            return json.loads(cached), True

        stats = await self.repo.stats()
        settings = get_settings()
        await redis_client.set(STATS_CACHE_KEY, json.dumps(stats), ex=settings.stats_cache_ttl)
        return stats, False
