"""Telegram Market Brief formatting (desk digest)."""

from datetime import datetime, timezone

from app.models.schemas import BriefStance, BriefTldr, MarketBrief
from app.services.brief_telegram import format_market_brief_telegram, stance_badge


def _sample_brief(**overrides) -> MarketBrief:
    base = dict(
        headline="Top3 whales lean short",
        market_status=(
            "Top3 whale book remains 73% short / 27% long, signaling near-term "
            "sell-side pressure from tracked-whale inventory. Funding stays near "
            "flat on majors. One-hour liquidations flushed longs for $0.6M."
        ),
        stance=BriefStance.PREFER_SHORT,
        suggestions=["Cut or avoid fresh longs into the Top3 short lean."],
        risks=["A sharp short squeeze would invalidate the lean."],
        tldr=BriefTldr(
            now="BTC $86,300 · as of 2026-09-23 · funding +0.0013%",
            short_read=(
                "Tape soft: Top3 whale book is 27/73 short-heavy and "
                "1h liqs flushed $0.6M longs."
            ),
            however="However: funding near flat — not a one-way squeeze tape.",
        ),
        as_of=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
        snapshot_hash="abc123",
        source="template",
        provider="template",
    )
    base.update(overrides)
    return MarketBrief(**base)


def test_stance_badge_labels():
    assert stance_badge(BriefStance.PREFER_SHORT) == "SHORT lean"
    assert stance_badge(BriefStance.PREFER_LONG) == "LONG lean"
    assert stance_badge(BriefStance.WAIT) == "WAIT"


def test_format_market_brief_telegram_structure():
    title, lines = format_market_brief_telegram(_sample_brief())
    text = "\n".join(lines)
    assert title.startswith("MARKET BRIEF")
    assert "• BTC $86,300" in text
    assert "• Tape soft:" in text
    assert "• However:" in text
    assert "Stance · SHORT lean" in text
    assert "Note ·" in text
    # Prefer stays off TL;DR bullets
    assert "Prefer" not in lines[1]
    assert "Prefer" not in lines[2]
    assert "Prefer" not in lines[3]


def test_format_stale_title():
    title, _ = format_market_brief_telegram(_sample_brief(stale=True))
    assert "STALE" in title
