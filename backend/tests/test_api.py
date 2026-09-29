import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import get_session
from app.main import app
from app.models import Base
from app.providers.cache import rate_limiter as rate_limiter_module
from app.providers.triage.simulated import SimulatedTriage
from app.routes import health as health_module
from app.services import complaint_service as complaint_service_module
from app.services import stats_service as stats_service_module
from app.services import triage_service as triage_service_module
from app.services.triage_service import TriageService

GOOD = {"text": "Burst water main flooding the street", "location": "Sector G-9"}


@pytest_asyncio.fixture
async def client(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _add_char_length(dbapi_conn, _):
        dbapi_conn.create_function("char_length", 1, len)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session():
        async with Session() as session:
            yield session

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for module in (rate_limiter_module, complaint_service_module, stats_service_module,
                   triage_service_module, health_module):
        monkeypatch.setattr(module, "redis_client", fake)
    monkeypatch.setattr(health_module, "engine", engine)
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 1000, raising=False)

    app.dependency_overrides[get_session] = override_session
    app.state.triage_service = TriageService(SimulatedTriage())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


async def _create(client, **overrides):
    resp = await client.post("/api/complaints", json={**GOOD, **overrides})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_and_get_complaint(client):
    created = await _create(client)
    assert created["status"] == "open"
    assert created["triaged_by"] == "simulated"
    resp = await client.get(f"/api/complaints/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_unknown_complaint_is_404(client):
    resp = await client.get("/api/complaints/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_body_gives_400_with_field_errors(client):
    resp = await client.post("/api/complaints", json={"text": "short", "location": "x"})
    assert resp.status_code == 400
    fields = {e["loc"][-1] for e in resp.json()["errors"]}
    assert {"text", "location"} <= fields


@pytest.mark.asyncio
async def test_list_pagination_and_filters(client):
    for i in range(5):
        await _create(client, text=f"Complaint number {i} about a broken road")
    resp = await client.get("/api/complaints", params={"page": 1, "page_size": 2})
    body = resp.json()
    assert body["total"] == 5 and len(body["items"]) == 2
    resp = await client.get("/api/complaints", params={"status": "resolved"})
    assert resp.json()["total"] == 0
    first = (await client.get("/api/complaints")).json()["items"][0]
    resp = await client.get("/api/complaints", params={"category": first["category"], "priority": first["priority"]})
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_page_size_over_100_is_rejected(client):
    resp = await client.get("/api/complaints", params={"page_size": 101})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_valid_status_transition(client):
    created = await _create(client)
    resp = await client.patch(f"/api/complaints/{created['id']}/status", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_invalid_status_transition_is_409_naming_transition(client):
    created = await _create(client)
    resp = await client.patch(f"/api/complaints/{created['id']}/status", json={"status": "resolved"})
    assert resp.status_code == 409
    assert "open to resolved" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_status_patch_unknown_id_is_404(client):
    resp = await client.patch(
        "/api/complaints/00000000-0000-0000-0000-000000000000/status", json={"status": "rejected"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stats_miss_then_hit_then_invalidated_on_write(client):
    await _create(client)
    first = await client.get("/api/stats")
    assert first.headers["x-cache"] == "MISS"
    assert first.json()["total"] == 1
    assert (await client.get("/api/stats")).headers["x-cache"] == "HIT"
    await _create(client, text="Another complaint about a streetlight")
    after = await client.get("/api/stats")
    assert after.headers["x-cache"] == "MISS"
    assert after.json()["total"] == 2


@pytest.mark.asyncio
async def test_meta_providers_reports_outcomes(client):
    await _create(client)
    body = (await client.get("/api/meta/providers")).json()
    assert body["active_provider"] == "simulated"
    assert len(body["recent_outcomes"]) == 1


@pytest.mark.asyncio
async def test_health_ready_and_metrics(client):
    assert (await client.get("/health")).json() == {"status": "alive"}
    assert (await client.get("/ready")).status_code == 200
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text


@pytest.mark.asyncio
async def test_ready_returns_503_naming_failed_dependency(client, monkeypatch):
    class BrokenRedis:
        async def ping(self):
            raise ConnectionError("down")

    monkeypatch.setattr(health_module, "redis_client", BrokenRedis())
    resp = await client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["failed"] == ["redis"]


@pytest.mark.asyncio
async def test_request_id_is_propagated_and_generated(client):
    resp = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"
    assert (await client.get("/health")).headers["x-request-id"]


@pytest.mark.asyncio
async def test_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 2, raising=False)
    await _create(client)
    await _create(client)
    resp = await client.post("/api/complaints", json=GOOD)
    assert resp.status_code == 429
    assert int(resp.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_failing_provider_still_returns_201_with_fallback(client):
    app.state.triage_service = TriageService(SimulatedTriage(fail_mode="raise"))
    created = await _create(client)
    assert created["triaged_by"] == "rules:fallback"
