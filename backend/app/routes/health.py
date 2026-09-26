"""
/health and /ready are deliberately different (§2.2): a failing liveness
probe restarts the pod, a failing readiness probe just removes it from the
Service. /health must NEVER touch the database -- if it did, a slow
Postgres would turn into a restart loop across the whole deployment,
because Kubernetes would keep killing pods that are actually fine.
"""
from fastapi import APIRouter, Response
from sqlalchemy import text
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ..database import engine
from ..providers.cache.redis_client import redis_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness: process is alive. No I/O, on purpose."""
    return {"status": "alive"}


@router.get("/ready")
async def ready(response: Response):
    """Readiness: 200 only if Postgres AND Redis are both reachable."""
    failed = []
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        failed.append("postgres")

    try:
        await redis_client.ping()
    except Exception:
        failed.append("redis")

    if failed:
        response.status_code = 503
        return {"status": "not ready", "failed": failed}
    return {"status": "ready"}


@router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
