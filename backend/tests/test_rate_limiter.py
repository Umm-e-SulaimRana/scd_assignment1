import fakeredis.aioredis
import pytest

from app.providers.cache import rate_limiter as rate_limiter_module
from app.config import get_settings


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(rate_limiter_module, "redis_client", fake)
    yield


@pytest.mark.asyncio
async def test_requests_within_limit_are_allowed(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3, raising=False)
    for _ in range(3):
        result = await rate_limiter_module.check_rate_limit("10.0.0.1")
        assert result.allowed is True


@pytest.mark.asyncio
async def test_requests_over_limit_are_blocked_with_retry_after(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2, raising=False)

    await rate_limiter_module.check_rate_limit("10.0.0.2")
    await rate_limiter_module.check_rate_limit("10.0.0.2")
    blocked = await rate_limiter_module.check_rate_limit("10.0.0.2")

    assert blocked.allowed is False
    assert blocked.retry_after > 0


@pytest.mark.asyncio
async def test_different_ips_have_independent_limits(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1, raising=False)

    a = await rate_limiter_module.check_rate_limit("10.0.0.3")
    b = await rate_limiter_module.check_rate_limit("10.0.0.4")
    assert a.allowed is True
    assert b.allowed is True
