"""
SQLAlchemy 2.0 ORM models -- this is the ONLY file that defines the schema
shape in Python; Alembic migrations (alembic/versions/) are the only thing
allowed to change it in the actual database. No CREATE TABLE at app startup.
"""
import uuid
import datetime

from sqlalchemy import String, Integer, DateTime, Enum as SAEnum, Index, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

from .schemas import Category, Priority, Status


class Base(DeclarativeBase):
    pass


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)

    category: Mapped[Category] = mapped_column(
        SAEnum(Category, name="category_enum", values_callable=_enum_values), nullable=False
    )
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority, name="priority_enum", values_callable=_enum_values), nullable=False
    )
    status: Mapped[Status] = mapped_column(
        SAEnum(Status, name="status_enum", values_callable=_enum_values),
        nullable=False,
        default=Status.open,
        server_default=Status.open.value,
    )

    ai_summary: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # llm:groq | llm:ollama | rules | rules:fallback
    triaged_by: Mapped[str] = mapped_column(String(50), nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        # Serves: GET /api/complaints filtered/sorted by status+priority (dashboard default view)
        Index("ix_complaints_status_priority", "status", "priority"),
        # Serves: GET /api/complaints ordered by created_at desc (recency feed), and any date-range query
        Index("ix_complaints_created_at", "created_at"),
        CheckConstraint("char_length(text) >= 10 AND char_length(text) <= 2000", name="ck_text_length"),
        CheckConstraint("char_length(location) >= 3 AND char_length(location) <= 200", name="ck_location_length"),
    )
