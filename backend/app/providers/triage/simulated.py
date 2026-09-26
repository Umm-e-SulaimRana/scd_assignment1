"""
SimulatedTriage -- deterministic fake with configurable failure injection.
This is what pins CI: same input -> same output, every run, no network,
and it can be told to raise or return malformed data so we can test the
fallback path and the validator without depending on a real, flaky LLM.
"""
import hashlib

from ...schemas import TriageResult, Category, Priority


class SimulatedTriage:
    name = "simulated"

    def __init__(self, fail_mode: str | None = None):
        # fail_mode: None (normal) | "raise" (simulate timeout/5xx) | "malformed" (bad output)
        self.fail_mode = fail_mode

    async def triage(self, text: str, location: str) -> TriageResult:
        if self.fail_mode == "raise":
            raise RuntimeError("SimulatedTriage: injected failure for testing")
        if self.fail_mode == "malformed":
            # Simulates an LLM returning something that fails Pydantic validation
            raise ValueError("SimulatedTriage: malformed output for testing")

        digest = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        categories, priorities = list(Category), list(Priority)
        category = categories[digest % len(categories)]
        priority = priorities[(digest // 7) % len(priorities)]

        summary = " ".join(text.strip().split())
        if len(summary) > 140:
            summary = summary[:137] + "..."

        return TriageResult(category=category, priority=priority, summary=summary, confidence=0.9)
