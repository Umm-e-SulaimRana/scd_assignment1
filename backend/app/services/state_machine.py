"""
Explicit status transition table (§2.2 domain rules), not a chain of ifs.
This is the whole state machine, in one place, and it's the thing a viva
question will ask you to justify.
"""
from ..schemas import Status

TRANSITIONS: dict[Status, set[Status]] = {
    Status.open: {Status.in_progress, Status.rejected},
    Status.in_progress: {Status.resolved, Status.rejected},
    Status.resolved: set(),   # terminal
    Status.rejected: set(),   # terminal
}


class InvalidTransitionError(Exception):
    def __init__(self, current: Status, attempted: Status):
        self.current = current
        self.attempted = attempted
        super().__init__(f"Cannot transition from {current.value} to {attempted.value}")


def validate_transition(current: Status, new: Status) -> None:
    if new not in TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(current, new)
