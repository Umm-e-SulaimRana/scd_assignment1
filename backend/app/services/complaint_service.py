"""
Business-rule orchestration for creating a complaint: triage it, persist
it, invalidate the stats cache so the new complaint is reflected
immediately rather than up to 30s later (§2.4 Job 1).
"""
import uuid

from ..models import Complaint
from ..repositories.complaint_repository import ComplaintRepository
from ..services.triage_service import TriageService
from ..providers.cache.redis_client import redis_client
from ..schemas import ComplaintCreate, Status

STATS_CACHE_KEY = "stats:aggregate"


class ComplaintService:
    def __init__(self, repo: ComplaintRepository, triage_service: TriageService):
        self.repo = repo
        self.triage_service = triage_service

    async def create_complaint(self, payload: ComplaintCreate) -> Complaint:
        result, triaged_by, latency_ms = await self.triage_service.triage(payload.text, payload.location)

        complaint = Complaint(
            id=uuid.uuid4(),
            text=payload.text,
            location=payload.location,
            reporter_contact=payload.reporter_contact,
            category=result.category,
            priority=result.priority,
            status=Status.open,
            ai_summary=result.summary,
            triaged_by=triaged_by,
            triage_latency_ms=latency_ms,
        )
        created = await self.repo.create(complaint)
        await redis_client.delete(STATS_CACHE_KEY)
        return created
