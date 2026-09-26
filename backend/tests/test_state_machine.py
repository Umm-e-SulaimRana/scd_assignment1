import pytest

from app.schemas import Status
from app.services.state_machine import validate_transition, InvalidTransitionError


def test_valid_transitions_pass():
    validate_transition(Status.open, Status.in_progress)
    validate_transition(Status.open, Status.rejected)
    validate_transition(Status.in_progress, Status.resolved)
    validate_transition(Status.in_progress, Status.rejected)


@pytest.mark.parametrize(
    "current,attempted",
    [
        (Status.resolved, Status.open),
        (Status.resolved, Status.in_progress),
        (Status.rejected, Status.in_progress),
        (Status.open, Status.resolved),   # can't skip in_progress
        (Status.in_progress, Status.open),  # no going backwards
    ],
)
def test_invalid_transitions_raise_409_worthy_error(current, attempted):
    with pytest.raises(InvalidTransitionError):
        validate_transition(current, attempted)
