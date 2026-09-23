"""Rule-built Market Brief digest: tape, positioning, calibrated read."""

from app.models.schemas import BriefStance
from app.services.brief_report import (
    FUNDING_INTERVAL_LABEL,
    build_brief_digest,
    build_tldr_slots,
    coverage_band,
    coverage_label,
)
from tests.conftest import sample_snapshot


def _all_short_snapshot():
    return sample_snapshot(
        top3_consensus={
            "assets": ["BTC", "ETH", "HYPE"],
            "per_asset": [
                {
                    "asset": "BTC",
                    "long_pct": 17.1,
                    "short_pct": 82.9,
                    "long_usd": 0.22e9,
                    "short_usd": 1.25e9,
                    "positioned": 40,
                },
                {
                    "asset": "ETH",
                    "long_pct": 20.3,
                    "short_pct": 79.7,
                    "long_usd": 0.08e9,
                    "short_usd": 0.31e9,
                    "positioned": 12,
                },
                {
                    "asset": "HYPE",
                    "long_pct": 27.3,
                    "short_pct": 72.7,
                    "long_usd": 0.03e9,
                    "short_usd": 0.08e9,
                    "positioned": 6,
                },
            ],
            "mood": "BEARISH",
            "long_pct": 20.0,
            "short_pct": 80.0,
            "reason": "Top3 short-heavy",
        },
        liq_1h={"long_usd": 80_000, "short_usd": 40_000, "total_usd": 120_000, "events": 4},
        coverage={"positioned": 58, "tracked": 100},
        tape={
            "BTC": {
                "asset": "BTC",
                "mark_price": 86224.0,
                "change_pct_24h": -0.3,
                "prev_day_price": 86480.0,
                "funding_pct": 0.0013,
                "open_interest": 2e6,
                "day_volume_usd": 900e6,
                "updated_at": "2026-09-23T12:00:00+00:00",
            },
            "ETH": {
                "asset": "ETH",
                "mark_price": 4120.0,
                "change_pct_24h": -0.2,
                "funding_pct": 0.0010,
                "day_volume_usd": 400e6,
            },
            "HYPE": {
                "asset": "HYPE",
                "mark_price": 42.5,
                "change_pct_24h": -1.1,
                "funding_pct": 0.0008,
                "day_volume_usd": 300e6,
            },
        },
        as_of="2026-09-23T12:00:00+00:00",
        top3_funding=[
            {"asset": "BTC", "funding_pct": 0.0013, "is_extreme": False, "note": "x"},
            {"asset": "ETH", "funding_pct": 0.0010, "is_extreme": False, "note": "x"},
            {"asset": "HYPE", "funding_pct": 0.0008, "is_extreme": False, "note": "x"},
        ],
    )


def test_coverage_bands():
    assert coverage_band(sample_snapshot(coverage={"positioned": 20, "tracked": 100})) == "Low"
    assert coverage_band(sample_snapshot(coverage={"positioned": 58, "tracked": 100})) == "Medium"
    assert coverage_band(sample_snapshot(coverage={"positioned": 80, "tracked": 100})) == "High"
    assert coverage_label(_all_short_snapshot()) == "58/100 (Medium)"


def test_digest_matches_labeled_brief_shape():
    digest = build_brief_digest(_all_short_snapshot(), None, BriefStance.PREFER_SHORT)
    assert digest.as_of_line.startswith("As of 2026-09-23 | BTC $86,224")
    assert "-0.3% vs prev day" in digest.as_of_line
    assert digest.funding_line == f"Funding ({FUNDING_INTERVAL_LABEL}) +0.0013%"
    assert FUNDING_INTERVAL_LABEL == "1h"
    assert digest.positioning[0].startswith("Tracked book: 20% long / 80% short")
    assert "net short ~$1.31B" in digest.positioning[0]
    assert digest.positioning[1] == (
        "By asset: BTC 82.9% short · ETH 79.7% short · HYPE 72.7% short"
    )
    assert digest.positioning[2] == "Liquidations (1h): quiet"
    assert digest.positioning[3] == "Coverage: 58/100 (Medium)"
    assert "short-heavy across all 3 assets" in digest.read
    assert "not high-confidence" in digest.read
    assert "significant sell" not in digest.read.lower()
    assert "not confirmation" in digest.note
    assert digest.coverage_band == "Medium"


def test_tldr_now_names_lead_asset_and_hourly_funding():
    tldr = build_tldr_slots(_all_short_snapshot())
    assert tldr.now.startswith("BTC $86,224")
    assert "funding (1h)" in tldr.now
    assert "HYPE/BTC/ETH" not in tldr.now
