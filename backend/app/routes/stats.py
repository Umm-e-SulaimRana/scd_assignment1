from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..repositories.complaint_repository import ComplaintRepository
from ..services.stats_service import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats(response: Response, session: AsyncSession = Depends(get_session)):
    repo = ComplaintRepository(session)
    service = StatsService(repo)
    stats, hit = await service.get_stats()
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return stats
