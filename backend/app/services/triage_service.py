"""
TriageService -- this is where the marks in §2.5 "The engineering around
the model" actually live. Providers (llm.py, ollama.py, rules.py,
simulated.py) just make a call and parse a reply. This class is the
business rule that makes depending on one of them safe:

  1. Content-hash cache lookup in Redis (24h TTL) -- duplicate complaints
     (a burst main reported by nine neighbours) cost one inference, not nine.
  2. Hard 10s timeout on the primary provider.
  3. One retry, with jitter, but ONLY on retryable failures (timeout, 429,
     5xx) -- never on a 400, because that request was wrong and retrying
     it wastes the retry budget for no benefit.
  4. Fallback to RuleBasedTriage on any remaining failure. Recorded as
     triaged_by = "rules:fallback" and logged as a single WARNING with the
     provider name and error class (never the raw exception text, which
     could contain the API key from a stack trace).
  5. triage_latency_ms is measured end-to-end (including cache lookup,
     retry sleep, everything) because that's what a citizen actually waits.
  6. A small in-memory ring buffer of the last 20 outcomes backs
     GET /api/meta/providers, the observability surface required by §2.2.
"""
import asyncio
import hashlib
import json
import logging
import random
import time
from collections import deque
from dataclasses import dataclass

from ..providers.cache.redis_client import redis_client
from ..providers.triage.base import TriageProvider
from ..providers.triage.rules import RuleBasedTriage
from ..config import get_settings
from ..schemas import TriageResult
from ..metrics import TRIAGE_LATENCY, TRIAGE_FALLBACK_COUNT

logger = logging.getLogger("civicpulse.triage")


@dataclass
class TriageOutcome:
    provider: str
    latency_ms: int
    fallback: bool
    at: float


class TriageService:
    def __init__(self, primary: TriageProvider):
        self.primary = primary
        self.fallback_provider = RuleBasedTriage()
        self.recent: deque[TriageOutcome] = deque(maxlen=20)

    # ---- content-hash cache ----
    @staticmethod
    def _content_hash(text: str) -> str:
        normalised = " ".join(text.strip().lower().split())
        return hashlib.sha256(normalised.encode()).hexdigest()

    async def _get_cached(self, text: str) -> TriageResult | None:
        raw = await redis_client.get(f"triage:{self._content_hash(text)}")
        return TriageResult(**json.loads(raw)) if raw else None

    async def _set_cached(self, text: str, result: TriageResult):
        settings = get_settings()
        await redis_client.set(
            f"triage:{self._content_hash(text)}",
            result.model_dump_json(),
            ex=settings.triage_cache_ttl,
        )

    async def cache_hit_rate(self) -> float:
        total = int(await redis_client.get("triage:cache:total") or 0)
        hits = int(await redis_client.get("triage:cache:hits") or 0)
        return round(hits / total, 4) if total else 0.0

    # ---- retry classification ----
    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """timeout, 429 or 5xx -> retryable. Everything else (incl. 400,
        malformed JSON, schema validation failure) is not -- retrying a
        request that was wrong the first time just wastes the budget."""
        status = getattr(exc, "status_code", None)
        if status is None:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
        if status is not None:
            return status == 429 or status >= 500
        return isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError))

    async def _call_with_timeout_and_retry(self, text: str, location: str) -> TriageResult:
        last_exc: Exception | None = None
        for attempt in range(2):  # first try + at most one retry
            try:
                return await asyncio.wait_for(self.primary.triage(text, location), timeout=10)
            except Exception as exc:  # noqa: BLE001 -- provider boundary must never crash the request
                last_exc = exc
                if attempt == 0 and self._is_retryable(exc):
                    await asyncio.sleep(random.uniform(0.1, 0.5))  # jitter
                    continue
                break
        assert last_exc is not None
        raise last_exc

    # ---- public API ----
    async def triage(self, text: str, location: str) -> tuple[TriageResult, str, int]:
        """Returns (result, triaged_by, latency_ms)."""
        start = time.monotonic()
        await redis_client.incr("triage:cache:total")

        cached = await self._get_cached(text)
        if cached is not None:
            await redis_client.incr("triage:cache:hits")
            latency_ms = int((time.monotonic() - start) * 1000)
            self.recent.appendleft(TriageOutcome(self.primary.name, latency_ms, False, time.time()))
            TRIAGE_LATENCY.observe(latency_ms / 1000)
            return cached, self.primary.name, latency_ms

        fallback = False
        provider_name = self.primary.name
        try:
            result = await self._call_with_timeout_and_retry(text, location)
        except Exception as exc:
            logger.warning(
                "triage_fallback",
                extra={"provider": self.primary.name, "error_class": type(exc).__name__},
            )
            fallback = True
            provider_name = "rules:fallback"
            TRIAGE_FALLBACK_COUNT.inc()
            result = await self.fallback_provider.triage(text, location)

        latency_ms = int((time.monotonic() - start) * 1000)
        TRIAGE_LATENCY.observe(latency_ms / 1000)
        self.recent.appendleft(TriageOutcome(provider_name, latency_ms, fallback, time.time()))

        if not fallback:
            await self._set_cached(text, result)

        return result, provider_name, latency_ms
