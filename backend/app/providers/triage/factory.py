"""
Reads TRIAGE_PROVIDER and builds the primary provider. This is the single
place environment-variable selection happens -- everything downstream just
sees "a TriageProvider".
"""
from ...config import get_settings
from .base import TriageProvider
from .rules import RuleBasedTriage
from .simulated import SimulatedTriage
from .llm import LLMTriage
from .ollama import OllamaTriage


def build_primary_provider() -> TriageProvider:
    settings = get_settings()
    provider = settings.triage_provider
    if provider == "llm":
        return LLMTriage()
    if provider == "ollama":
        return OllamaTriage()
    if provider == "rules":
        return RuleBasedTriage()
    if provider == "simulated":
        return SimulatedTriage()
    raise ValueError(f"Unknown TRIAGE_PROVIDER: {provider!r} (expected llm|ollama|rules|simulated)")
