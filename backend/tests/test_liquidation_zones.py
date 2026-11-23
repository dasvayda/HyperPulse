from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models.schemas import WhalePosition
from app.services.store import store
from app.services.liquidation_zones import tracked_liquidation_zones

NOW = datetime(2026, 11, 24, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(settings, "alert_min_size_usd", 500_000)
    monkeypatch.setattr(settings, "collector_interval_seconds", 60)
    monkeypatch.setattr(store, "whale_positions", [])
    monkeypatch.setattr(store, "whale_observed_at", {})
    monkeypatch.setattr(store, "market_ticks", {
        "BTC": {"mark_price": 100, "open_interest": 1_000_000, "updated_at": NOW},
    })


def position(wallet="a", **kwargs):
    store.whale_observed_at[wallet] = NOW
    row = WhalePosition(**{"trader_address": wallet, "asset": "BTC", "side": "long",
                           "size_usd": 1_000_000, "entry_price": 100, "leverage": 10,
                           "liquidation_px": 95, **kwargs})
    store.whale_positions.append(row)
    return row


def test_weighted_band_separates_actual_from_model_without_fake_history():
    position("a", size_usd=1_000_000, liquidation_px=95)
    position("b", size_usd=3_000_000, liquidation_px=94.5)
    position("c", liquidation_px=None, leverage=18)
    zones = tracked_liquidation_zones(now=NOW)
    assert len(zones) == 2
    actual = next(z for z in zones if z.source == "liquidationPx")
    assert actual.price == pytest.approx(94.625)
    assert actual.size_usd == 4_000_000
    assert actual.positions == actual.wallets == 2
    assert actual.open_interest_pct == 4
    assert actual.sparkline == []
    assert actual.observed_at == NOW
    assert all(z.scope == "tracked_wallets" for z in zones)


def test_stale_wallet_or_mark_invalid_estimate_and_tiny_positions_are_excluded():
    position("stale")
    store.whale_observed_at["stale"] = NOW - timedelta(minutes=10)
    position("tiny", size_usd=1)
    position("passed", side="short", entry_price=50, liquidation_px=None)
    position("far", liquidation_px=10)
    assert tracked_liquidation_zones(now=NOW) == []
    position("fresh")
    assert len(tracked_liquidation_zones(now=NOW)) == 1
    store.market_ticks["BTC"]["updated_at"] = NOW - timedelta(minutes=10)
    assert tracked_liquidation_zones(now=NOW) == []


def test_direction_bands_and_live_endpoint(monkeypatch):
    position("long", liquidation_px=95)
    position("short", side="short", liquidation_px=105)
    monkeypatch.setattr(settings, "use_mock_data", False)
    from app.routers.api import list_liquidation_zones
    # The route uses the real current clock; provide fresh observation times.
    now = datetime.now(timezone.utc)
    store.whale_observed_at = {"long": now, "short": now}
    store.market_ticks["BTC"]["updated_at"] = now
    zones = list_liquidation_zones(asset="BTC")
    assert len(zones) == 2
    assert {z.distance_pct for z in zones} == {-5, 5}
    assert list_liquidation_zones(asset="ETH") == []
