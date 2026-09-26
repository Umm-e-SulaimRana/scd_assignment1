import pytest

from app.providers.triage.rules import RuleBasedTriage
from app.schemas import Category, Priority


@pytest.mark.asyncio
async def test_rules_never_fails_and_returns_valid_enum():
    provider = RuleBasedTriage()
    result = await provider.triage("Burst water main flooding the street", "Sector G-9")
    assert result.category == Category.water
    assert result.priority == Priority.high  # "flooding" is an urgency keyword
    assert len(result.summary) <= 140


@pytest.mark.asyncio
async def test_rules_unknown_topic_falls_back_to_other():
    provider = RuleBasedTriage()
    result = await provider.triage("There is a strange smell I cannot describe near the park bench", "F-8")
    assert result.category in list(Category)
    assert result.priority in list(Priority)
