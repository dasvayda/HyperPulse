from datetime import datetime, timedelta, timezone

from app.models.schemas import (
    AssetWhaleSummary,
    LiquidationEvent,
    LiquidationSide,
    WhaleBookSummary,
)
from app.services.store import store

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)


def sample_snapshot(**overrides):
    payload = {
        "as_of": NOW.isoformat(),
        "top3_consensus": {
            "assets": ["HYPE", "BTC", "ETH"],
            "per_asset": [
                {
                    "asset": "HYPE",
                    "long_pct": 40.0,
                    "short_pct": 60.0,
                    "long_usd": 20e6,
                    "short_usd": 30e6,
                    "positioned": 12,
                },
                {
                    "asset": "BTC",
                    "long_pct": 38.0,
                    "short_pct": 62.0,
                    "long_usd": 40e6,
                    "short_usd": 65e6,
                    "positioned": 20,
                },
                {
                    "asset": "ETH",
                    "long_pct": 66.0,
                    "short_pct": 34.0,
                    "long_usd": 22e6,
                    "short_usd": 11e6,
                    "positioned": 14,
                },
            ],
            "mood": "BEARISH",
            "long_pct": 40.0,
            "short_pct": 60.0,
            "reason": "Top3 short-heavy",
        },
        "book_wide": {
            "long_pct": 41.0,
            "short_pct": 59.0,
            "long_usd": 90e6,
            "short_usd": 120e6,
            "net_bias": "short",
            "positioned": 55,
            "tracked": 100,
        },
        "coin_stances": [
            {"asset": "BTC", "stance": "prefer_short", "signals": ["Whale L/S: 38/62"], "confidence": 70},
            {"asset": "ETH", "stance": "prefer_long", "signals": ["Whale L/S: 66/34"], "confidence": 68},
        ],
        "top3_funding": [
            {"asset": "HYPE", "funding_pct": 0.004, "is_extreme": False, "note": "x"},
            {"asset": "BTC", "funding_pct": 0.005, "is_extreme": False, "note": "x"},
            {"asset": "ETH", "funding_pct": -0.003, "is_extreme": False, "note": "x"},
        ],
        "extreme_funding": [],
        "liq_1h": {"long_usd": 2.1e6, "short_usd": 0.4e6, "total_usd": 2.5e6, "events": 40},
        "liq_24h": {"long_usd": 18e6, "short_usd": 9e6, "total_usd": 27e6, "events": 200},
        "liq_1h_by_asset": {
            "HYPE": {"long_usd": 0.2e6, "short_usd": 0.1e6, "total_usd": 0.3e6, "events": 4},
            "BTC": {"long_usd": 2.0e6, "short_usd": 0.3e6, "total_usd": 2.3e6, "events": 30},
            "ETH": {"long_usd": 0.05e6, "short_usd": 0.04e6, "total_usd": 0.09e6, "events": 2},
        },
        "liq_24h_by_asset": {
            "HYPE": {"long_usd": 2e6, "short_usd": 1e6, "total_usd": 3e6, "events": 20},
            "BTC": {"long_usd": 12e6, "short_usd": 5e6, "total_usd": 17e6, "events": 80},
            "ETH": {"long_usd": 8e6, "short_usd": 1e6, "total_usd": 9e6, "events": 40},
        },
        "tape": {
            "HYPE": {
                "asset": "HYPE",
                "mark_price": 42.5,
                "change_pct_24h": -1.8,
                "prev_day_price": 43.3,
                "funding_pct": 0.004,
                "open_interest": 1e6,
                "day_volume_usd": 900e6,
                "updated_at": NOW.isoformat(),
            },
            "BTC": {
                "asset": "BTC",
                "mark_price": 76844.0,
                "change_pct_24h": -2.1,
                "prev_day_price": 78490.0,
                "funding_pct": 0.005,
                "open_interest": 2e6,
                "day_volume_usd": 800e6,
                "updated_at": NOW.isoformat(),
            },
            "ETH": {
                "asset": "ETH",
                "mark_price": 4120.0,
                "change_pct_24h": 0.4,
                "prev_day_price": 4104.0,
                "funding_pct": -0.003,
                "open_interest": 1.2e6,
                "day_volume_usd": 500e6,
                "updated_at": NOW.isoformat(),
            },
        },
        "book_updated_at": NOW.isoformat(),
        "tape_updated_at": NOW.isoformat(),
        "biggest_positions": [{"asset": "BTC", "side": "short", "size_usd": 12e6, "alias": "w1"}],
        "coverage": {"positioned": 55, "tracked": 100},
        "snapshot_hash": "testhash",
    }
    payload.update(overrides)
    return payload


def seed_store() -> None:
    now = NOW
    store.market_ticks = {
        "HYPE": {
            "asset": "HYPE",
            "mark_price": 42.5,
            "change_pct_24h": -1.8,
            "prev_day_price": 43.3,
            "funding_rate": 0.00004,
            "open_interest": 1e6,
            "day_volume_usd": 900e6,
            "updated_at": now,
        },
        "BTC": {
            "asset": "BTC",
            "mark_price": 76844.0,
            "change_pct_24h": -2.1,
            "prev_day_price": 78490.0,
            "funding_rate": 0.00005,
            "open_interest": 2e6,
            "day_volume_usd": 800e6,
            "updated_at": now,
        },
        "ETH": {
            "asset": "ETH",
            "mark_price": 4120.0,
            "change_pct_24h": 0.4,
            "prev_day_price": 4104.0,
            "funding_rate": -0.00003,
            "open_interest": 1.2e6,
            "day_volume_usd": 500e6,
            "updated_at": now,
        },
    }
    store.whale_summary = WhaleBookSummary(
        tracked=100,
        with_positions=55,
        long_notional_usd=82e6,
        short_notional_usd=106e6,
        long_pct=40.0,
        net_notional_usd=-24e6,
        net_bias="short",
        long_whale_count=20,
        short_whale_count=30,
        neutral_whale_count=5,
        whale_count_long_pct=40.0,
        updated_at=now,
        by_asset={
            "HYPE": AssetWhaleSummary(
                asset="HYPE",
                whales=12,
                long_notional_usd=20e6,
                short_notional_usd=30e6,
                long_pct=40.0,
                net_notional_usd=-10e6,
                net_bias="short",
                avg_leverage=8.0,
            ),
            "BTC": AssetWhaleSummary(
                asset="BTC",
                whales=20,
                long_notional_usd=40e6,
                short_notional_usd=65e6,
                long_pct=38.0,
                net_notional_usd=-25e6,
                net_bias="short",
                avg_leverage=10.0,
            ),
            "ETH": AssetWhaleSummary(
                asset="ETH",
                whales=14,
                long_notional_usd=22e6,
                short_notional_usd=11e6,
                long_pct=66.0,
                net_notional_usd=11e6,
                net_bias="long",
                avg_leverage=7.0,
            ),
        },
    )
    store.liquidation_events = [
        LiquidationEvent(
            id="l1",
            asset="BTC",
            side=LiquidationSide.LONG,
            size_usd=2_000_000,
            price=76800,
            timestamp=now - timedelta(minutes=10),
        ),
        LiquidationEvent(
            id="l2",
            asset="BTC",
            side=LiquidationSide.SHORT,
            size_usd=300_000,
            price=76900,
            timestamp=now - timedelta(minutes=20),
        ),
    ]
    store.whale_positions = []
    store.traders = []
    store.market_brief = None
    store.insights = []
