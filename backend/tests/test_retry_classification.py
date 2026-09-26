"""Never retry a 400 (§2.5 point 3); do retry timeouts/429/5xx."""
import pytest

from app.services.triage_service import TriageService
from app.providers.triage.simulated import SimulatedTriage


class _FakeHTTPError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.mark.parametrize("status_code,expected", [(400, False), (404, False), (429, True), (500, True), (503, True)])
def test_status_code_retry_classification(status_code, expected):
    service = TriageService(SimulatedTriage())
    assert service._is_retryable(_FakeHTTPError(status_code)) is expected


def test_timeout_is_retryable():
    service = TriageService(SimulatedTriage())
    assert service._is_retryable(TimeoutError()) is True


def test_arbitrary_value_error_is_not_retryable():
    service = TriageService(SimulatedTriage())
    assert service._is_retryable(ValueError("malformed json")) is False
