"""
OllamaTriage -- fully offline path. Same interface, same prompt discipline
as LLMTriage, but talks to a local Ollama container over plain HTTP instead
of a hosted API. No key, no network egress, no PII leaving the machine --
the trade-off you're meant to measure is speed/accuracy vs. that privacy
and cost guarantee (see docs/adr/0004-pii-and-data-governance.md).
"""
import json

import httpx

from ...config import get_settings
from ...schemas import TriageResult, Category, Priority
from .llm import SYSTEM_PROMPT


class OllamaTriage:
    name = "llm:ollama"

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_url
        self.model = settings.ollama_model

    async def triage(self, text: str, location: str) -> TriageResult:
        prompt = f"{SYSTEM_PROMPT}\n\n<complaint>\nTEXT: {text}\nLOCATION: {location}\n</complaint>"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "format": "json", "stream": False},
            )
            resp.raise_for_status()
            data = json.loads(resp.json()["response"])

        return TriageResult(
            category=Category(data["category"]),
            priority=Priority(data["priority"]),
            summary=str(data["summary"])[:140],
            confidence=float(data["confidence"]),
        )
