from datetime import datetime

from app.models.schemas import BriefStance
from app.services.market_brief import _validate_brief
from tests.conftest import sample_snapshot


def test_llm_prefer_in_headline_is_stripped():
    snap = sample_snapshot()
    status = (
        "Top3 whale book remains 60% short / 40% long, signaling near-term "
        "sell-side pressure from tracked-whale inventory. Funding stays near flat "
        "and last 1h sampled liquidations skew long."
    )
    brief = _validate_brief(
        {
            "headline": "Top3 short-heavy — Prefer shorts",
            "market_status": status,
            "stance": "prefer_short",
            "suggestions": ["Prefer shorts while the tracked book stays short-heavy."],
            "risks": ["Coverage is 55/100 positioned whales."],
            "evidence_refs": ["top3_consensus"],
        },
        snap,
        "openai",
    )
    assert brief is not None
    assert brief.tldr is not None
    assert "prefer" not in brief.headline.lower()
    assert "prefer" not in brief.tldr.now.lower()
    assert brief.stance == BriefStance.PREFER_SHORT
    assert isinstance(brief.as_of, datetime)
