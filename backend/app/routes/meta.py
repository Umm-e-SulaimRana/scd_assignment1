"""GET /api/meta/providers -- the observability surface required by §2.2."""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/providers")
async def providers(request: Request):
    triage_service = request.app.state.triage_service
    hit_rate = await triage_service.cache_hit_rate()
    return {
        "active_provider": triage_service.primary.name,
        "triage_cache_hit_rate": hit_rate,
        "recent_outcomes": [
            {"provider": o.provider, "latency_ms": o.latency_ms, "fallback": o.fallback, "at": o.at}
            for o in triage_service.recent
        ],
    }
