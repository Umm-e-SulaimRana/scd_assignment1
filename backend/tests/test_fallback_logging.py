import logging

import fakeredis.aioredis
import pytest

from app.providers.triage.simulated import SimulatedTriage
from app.services import triage_service as triage_service_module
from app.services.triage_service import TriageService


@pytest.mark.asyncio
async def test_fallback_logs_one_warning_with_complaint_id(monkeypatch, caplog):
    monkeypatch.setattr(triage_service_module, "redis_client", fakeredis.aioredis.FakeRedis(decode_responses=True))
    service = TriageService(SimulatedTriage(fail_mode="raise"))
    with caplog.at_level(logging.WARNING, logger="civicpulse.triage"):
        await service.triage("Water pipe burst", "G-9", complaint_id="abc-123")
    records = [r for r in caplog.records if r.getMessage() == "triage_fallback"]
    assert len(records) == 1
    assert records[0].complaint_id == "abc-123"
    assert records[0].error_class == "RuntimeError"
