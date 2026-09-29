"""
HTTP layer only: parse, validate, serialise, pick a status code. All
business logic delegates to services/; all SQL delegates to repositories/.
"""
import uuid

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..dependencies import get_triage_service
from ..repositories.complaint_repository import ComplaintRepository
from ..services.complaint_service import ComplaintService
from ..services.state_machine import validate_transition, InvalidTransitionError
from ..providers.cache.rate_limiter import check_rate_limit
from ..schemas import ComplaintCreate, ComplaintOut, ComplaintList, StatusUpdate

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("", response_model=ComplaintOut, status_code=201)
async def create_complaint(
    payload: ComplaintCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    triage_service=Depends(get_triage_service),
):
    rl = await check_rate_limit(_client_ip(request))
    if not rl.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Slow down and try again shortly.",
            headers={"Retry-After": str(rl.retry_after)},
        )

    repo = ComplaintRepository(session)
    service = ComplaintService(repo, triage_service)
    return await service.create_complaint(payload)


@router.get("/{complaint_id}", response_model=ComplaintOut)
async def get_complaint(complaint_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = ComplaintRepository(session)
    complaint = await repo.get_by_id(complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.get("", response_model=ComplaintList)
async def list_complaints(
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    repo = ComplaintRepository(session)
    items, total = await repo.list(
        category=category, priority=priority, status=status, page=page, page_size=page_size
    )
    # Explicit ORM -> schema conversion. ComplaintOut has from_attributes=True so
    # FastAPI would coerce these anyway, but doing it here makes the boundary
    # visible and keeps the declared return type honest.
    return ComplaintList(
        items=[ComplaintOut.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{complaint_id}/status", response_model=ComplaintOut)
async def update_status(
    complaint_id: uuid.UUID, payload: StatusUpdate, session: AsyncSession = Depends(get_session)
):
    repo = ComplaintRepository(session)
    complaint = await repo.get_by_id(complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    try:
        validate_transition(complaint.status, payload.status)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {exc.current.value} to {exc.attempted.value}",
        ) from exc

    return await repo.update_status(complaint_id, payload.status)
