"""
End-to-end HTTP-level test of the full request path. This needs a real
Postgres reachable at DATABASE_URL, so it's skipped unless RUN_DB_TESTS=1
is set -- that variable is exported in the CI "integration" job (see
ci.yml, owned by the frontend/DevOps half of the team) and can be set
locally once you've run `docker compose up -d database redis` and
`alembic upgrade head`.
"""
import os

import pytest
from httpx import AsyncClient, ASGITransport

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="Set RUN_DB_TESTS=1 with a live Postgres+Redis to run this test.",
)


@pytest.mark.asyncio
async def test_create_and_fetch_complaint():
    from app.main import app  # imported late so env vars above are already set

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/complaints",
            json={"text": "Burst water main flooding the street near our house", "location": "Sector G-9"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["triaged_by"] in {"simulated", "rules", "rules:fallback", "llm:groq", "llm:ollama"}

        complaint_id = body["id"]
        get_resp = await client.get(f"/api/complaints/{complaint_id}")
        assert get_resp.status_code == 200

        stats_resp = await client.get("/api/stats")
        assert stats_resp.status_code == 200
        assert "X-Cache" in stats_resp.headers
