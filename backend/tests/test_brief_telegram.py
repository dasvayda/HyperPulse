"""Telegram Market Brief formatting (labeled digest)."""

from datetime import datetime, timezone

from app.models.schemas import BriefDigest, BriefStance, BriefTldr, MarketBrief
from app.services.brief_telegram import format_market_brief_telegram, stance_badge


def _sample_brief(**overrides) -> MarketBrief:
    base = dict(
        headline="Top3 (BTC/ETH/HYPE) whales lean short",
        market_status=(
            "Book stays short-heavy across all three assets, funding not at "
            "extreme levels. Medium coverage — directional signal present but "
            "not high-confidence."
        ),
        stance=BriefStance.PREFER_SHORT,
        suggestions=[
            "Whale book skews short on BTC/ETH; positioning supports short bias, not confirmation."
        ],
        risks=["A sharp short squeeze would invalidate the lean."],
        tab_assets=["BTC", "ETH", "HYPE"],
        digest=BriefDigest(
            as_of_line="As of 2026-09-23 | BTC $86,224 (-0.3% vs prev day)",
            funding_line="Funding (1h) +0.0013%",
            positioning=[
                "Tracked book: 20% long / 80% short (net short ~$1.31B)",
                "By asset: BTC 82.9% short · ETH 79.7% short · HYPE 72.7% short",
                "Liquidations (1h): quiet",
                "Coverage: 58/100 (Medium)",
            ],
            read=(
                "Book stays short-heavy across all three assets, funding not at "
                "extreme levels. Medium coverage — directional signal present but "
                "not high-confidence."
            ),
            note=(
                "Whale book skews short on BTC/ETH; positioning supports short "
                "bias, not confirmation."
            ),
            coverage_band="Medium",
        ),
        tldr=BriefTldr(
            now="BTC $86,224 · as of 2026-09-23 · vs prev day -0.3% · funding (1h) +0.0013%",
            short_read="short-heavy: tracked book $0.3B long / $1.6B short (20/80) and sampled 1h liq quiet",
            however="tracked book stays short-heavy and funding is not extreme (coverage 58/100 (Medium))",
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
    assert title == "MARKET BRIEF · Top3 (BTC/ETH/HYPE)"
    assert "As of 2026-09-23 | BTC $86,224 (-0.3% vs prev day)" in text
    assert "Funding (1h) +0.0013%" in text
    assert "Funding (8h)" not in text
    assert "<b>Positioning</b>" in text
    assert "• Tracked book: 20% long / 80% short (net short ~$1.31B)" in text
    assert "• By asset: BTC 82.9% short" in text
    assert "• Liquidations (1h): quiet" in text
    assert "• Coverage: 58/100 (Medium)" in text
    assert "<b>Read</b>" in text
    assert "not high-confidence" in text
    assert "Stance · SHORT lean" in text
    assert "Note ·" in text
    assert "not confirmation" in text
    assert "significant sell pressure" not in text.lower()
    assert "strong bearish" not in text.lower()
    # Numbers appear once in Positioning, not dumped again as overlapping TL;DR
    assert text.count("20% long / 80% short") == 1
    assert "Prefer" not in text


def test_format_stale_title():
    title, _ = format_market_brief_telegram(_sample_brief(stale=True))
    assert title.startswith("MARKET BRIEF · STALE")
