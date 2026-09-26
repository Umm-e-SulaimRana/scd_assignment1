"""
The interface every triage backend implements. Pure Python Protocol, so
providers don't even need to inherit from anything -- they just need the
right shape. This is what makes "today it's a keyword rule, tomorrow it's
a language model" a non-event for the rest of the system (§1.1).
"""
from typing import Protocol

from ...schemas import TriageResult


class TriageProvider(Protocol):
    name: str

    async def triage(self, text: str, location: str) -> TriageResult: ...
