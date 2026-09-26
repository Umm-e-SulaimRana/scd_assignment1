"""
ALL SQL lives here and nowhere else (§2.2 layering). Routes never see a
session directly for anything but injecting it into a repository; services
never write raw SQL.
"""
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Complaint
from ..schemas import Status


class ComplaintRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, complaint: Complaint) -> Complaint:
        self.session.add(complaint)
        await self.session.commit()
        await self.session.refresh(complaint)
        return complaint

    async def get_by_id(self, complaint_id: uuid.UUID) -> Complaint | None:
        return await self.session.get(Complaint, complaint_id)

    async def list(
        self,
        *,
        category: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Complaint], int]:
        stmt = select(Complaint)
        count_stmt = select(func.count()).select_from(Complaint)

        if category:
            stmt = stmt.where(Complaint.category == category)
            count_stmt = count_stmt.where(Complaint.category == category)
        if priority:
            stmt = stmt.where(Complaint.priority == priority)
            count_stmt = count_stmt.where(Complaint.priority == priority)
        if status:
            stmt = stmt.where(Complaint.status == status)
            count_stmt = count_stmt.where(Complaint.status == status)

        stmt = stmt.order_by(Complaint.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

        total = (await self.session.execute(count_stmt)).scalar_one()
        items = list((await self.session.execute(stmt)).scalars().all())
        return items, total

    async def update_status(self, complaint_id: uuid.UUID, new_status: Status) -> Complaint | None:
        complaint = await self.get_by_id(complaint_id)
        if complaint is None:
            return None
        complaint.status = new_status
        await self.session.commit()
        await self.session.refresh(complaint)
        return complaint

    async def stats(self) -> dict:
        cat_stmt = select(Complaint.category, func.count()).group_by(Complaint.category)
        pri_stmt = select(Complaint.priority, func.count()).group_by(Complaint.priority)
        total_stmt = select(func.count()).select_from(Complaint)

        cat_rows = (await self.session.execute(cat_stmt)).all()
        pri_rows = (await self.session.execute(pri_stmt)).all()
        total = (await self.session.execute(total_stmt)).scalar_one()

        return {
            "total": total,
            "by_category": {c.value: n for c, n in cat_rows},
            "by_priority": {p.value: n for p, n in pri_rows},
        }
