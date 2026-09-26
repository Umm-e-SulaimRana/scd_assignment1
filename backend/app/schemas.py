"""
Pydantic v2 models. These do double duty (per the assignment's design intent):
  1. HTTP request/response validation for FastAPI routes.
  2. Validating untrusted LLM output before it ever touches the database.
One mental model, two uses -- see TriageResult below.
"""
import uuid
import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class Category(str, Enum):
    water = "water"
    electricity = "electricity"
    sanitation = "sanitation"
    roads = "roads"
    streetlights = "streetlights"
    other = "other"


class Priority(str, Enum):
    high = "high"
    normal = "normal"
    low = "low"


class Status(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


# ---- AI layer contract (§2.5) ----
class TriageResult(BaseModel):
    category: Category
    priority: Priority
    summary: str = Field(max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)


# ---- API request bodies ----
class ComplaintCreate(BaseModel):
    text: str = Field(min_length=10, max_length=2000)
    location: str = Field(min_length=3, max_length=200)
    reporter_contact: str | None = Field(default=None, max_length=200)


class StatusUpdate(BaseModel):
    status: Status


# ---- API response bodies ----
class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None
    triaged_by: str
    triage_latency_ms: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ComplaintList(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class TriageOutcomeOut(BaseModel):
    provider: str
    latency_ms: int
    fallback: bool
    at: float


class ProviderInfoOut(BaseModel):
    active_provider: str
    triage_cache_hit_rate: float
    recent_outcomes: list[TriageOutcomeOut]
