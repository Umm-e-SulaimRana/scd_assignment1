"""
RuleBasedTriage -- deterministic keyword matching. This is the fallback
that guarantees POST /api/complaints never 500s because a third-party LLM
is rate-limited, slow, or wrong (§2.5 point 4). It never calls the network
and it never fails.
"""
from ...schemas import TriageResult, Category, Priority

CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.water: ["water", "pipe", "burst main", "leak", "sewage flood", "tap", "supply", "tanker"],
    Category.electricity: ["electric", "wapda", "transformer", "wire", "power", "outage", "voltage", "short circuit", "current"],
    Category.sanitation: ["garbage", "trash", "sewage", "drain", "waste", "sanitation", "badbu", "smell", "gutter"],
    Category.roads: ["road", "pothole", "gaddha", "street damage", "construction", "footpath", "speed breaker"],
    Category.streetlights: ["streetlight", "street light", "lamp post", "khamba", "light not working", "andhera"],
}

URGENT_KEYWORDS = [
    "flood", "flooding", "fire", "burst", "danger", "khatarnak", "collapsed",
    "injur", "electrocut", "gas leak", "urgent", "emergency", "sparking",
]


class RuleBasedTriage:
    name = "rules"

    async def triage(self, text: str, location: str) -> TriageResult:
        lowered = text.lower()

        category = Category.other
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(k in lowered for k in keywords):
                category = cat
                break

        priority = Priority.high if any(k in lowered for k in URGENT_KEYWORDS) else Priority.normal

        summary = " ".join(text.strip().split())
        if len(summary) > 140:
            summary = summary[:137] + "..."

        return TriageResult(category=category, priority=priority, summary=summary, confidence=0.4)
