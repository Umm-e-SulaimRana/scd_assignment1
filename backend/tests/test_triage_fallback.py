"""
The one test the handout says to write above all others:
"given a provider that always raises, POST /api/complaints still returns
201 and triaged_by == 'rules:fallback'."

This file tests TriageService directly (unit-level, no real HTTP/DB
needed) with fakeredis standing in for Redis. The equivalent end-to-end
HTTP version lives in tests/test_complaints_api.py, which needs a real
Postgres and only runs in the compose integration job / when DATABASE_URL
points at a live database (see README "Running tests").
"""
import fakeredis.aioredis
import pytest

from app.providers.triage.simulated import SimulatedTriage
from app.services import triage_service as triage_service_module
from app.services.triage_service import TriageService


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(triage_service_module, "redis_client", fake)
    yield


@pytest.mark.asyncio
async def test_provider_that_always_raises_falls_back_to_rules():
    always_fails = SimulatedTriage(fail_mode="raise")
    service = TriageService(always_fails)

    result, triaged_by, latency_ms = await service.triage(
        "Burst water main flooding Street 12", "Sector G-9"
    )

    assert triaged_by == "rules:fallback"
    assert result.category is not None
    assert result.priority is not None
    assert latency_ms >= 0


@pytest.mark.asyncio
async def test_provider_returning_malformed_output_also_falls_back():
    malformed = SimulatedTriage(fail_mode="malformed")
    service = TriageService(malformed)

    result, triaged_by, latency_ms = await service.triage("Some complaint text here", "F-8")

    assert triaged_by == "rules:fallback"


@pytest.mark.asyncio
async def test_healthy_provider_is_used_and_cached():
    healthy = SimulatedTriage()
    service = TriageService(healthy)

    text = "Streetlight not working on main road for three days"
    result1, triaged_by1, _ = await service.triage(text, "DHA")
    assert triaged_by1 == "simulated"

    # Second call with identical text should hit the content-hash cache
    result2, triaged_by2, _ = await service.triage(text, "DHA")
    assert triaged_by2 == "simulated"
    assert result1.category == result2.category

    hit_rate = await service.cache_hit_rate()
    assert hit_rate > 0
