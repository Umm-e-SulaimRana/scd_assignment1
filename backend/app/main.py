"""
App assembly. Graceful shutdown (§2.2): the lifespan "shutdown" phase closes
the Redis and Postgres pools. In-flight-request draining itself is handled
by uvicorn on SIGTERM via --timeout-graceful-shutdown (set in the
Dockerfile CMD): uvicorn stops accepting new connections, waits for
in-flight requests to finish (up to the timeout), THEN triggers this
lifespan shutdown block. Without this, every Kubernetes rolling update
drops live requests.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import close_db
from .middleware import configure_logging, RequestIdMiddleware
from .metrics import REQUEST_COUNT, REQUEST_LATENCY
from .providers.cache.redis_client import close_redis
from .providers.triage.factory import build_primary_provider
from .services.triage_service import TriageService
from .routes import complaints, stats, meta, health

logger = logging.getLogger("civicpulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    # Built once, reused by every request via dependencies.get_triage_service
    app.state.triage_service = TriageService(build_primary_provider())
    logger.info("startup_complete", extra={"triage_provider": settings.triage_provider})

    yield

    # SIGTERM: uvicorn has already stopped taking new connections and
    # drained in-flight ones by the time we get here.
    await close_redis()
    await close_db()
    logger.info("shutdown_complete")


app = FastAPI(title="CivicPulse API", version="1.0.0", lifespan=lifespan)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    route = request.scope.get("route")
    path = route.path if route else request.url.path
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Field-level 400s, as required by POST /api/complaints in §2.2."""
    return JSONResponse(status_code=400, content={"detail": "Validation failed", "errors": exc.errors()})


app.include_router(health.router)
app.include_router(complaints.router)
app.include_router(stats.router)
app.include_router(meta.router)
