"""Shared FastAPI dependencies that don't belong to one route module."""
from fastapi import Request

from .services.triage_service import TriageService


def get_triage_service(request: Request) -> TriageService:
    """The TriageService is built once at startup (see main.py lifespan)
    and stored on app.state so every request reuses the same provider
    instance, connection pools and in-memory recent-outcomes ring buffer."""
    return request.app.state.triage_service
