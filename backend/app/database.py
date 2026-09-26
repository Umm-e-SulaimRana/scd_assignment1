"""
Async SQLAlchemy engine + session factory. One engine per process, reused
across requests via a connection pool (pool_pre_ping guards against stale
connections after Postgres restarts on Kubernetes).
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from .config import get_settings

_settings = get_settings()

engine = create_async_engine(_settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=5)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session():
    """FastAPI dependency: one session per request, closed automatically."""
    async with SessionLocal() as session:
        yield session


async def close_db():
    """Called on SIGTERM (see main.py lifespan) so the pool drains cleanly."""
    await engine.dispose()
