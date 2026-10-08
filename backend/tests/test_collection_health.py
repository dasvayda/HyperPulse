import asyncio

from app.collectors import hyperliquid
from app.config import settings
from app.services.readiness import get_readiness
from app.services.store import store
from tests.conftest import NOW


def test_failed_market_fetch_preserves_last_success_and_marks_degraded(monkeypatch):
    monkeypatch.setattr(settings, "use_mock_data", False)
    monkeypatch.setattr(settings, "collector_enabled", True)
    monkeypatch.setattr(store, "last_collect_at", NOW)
    monkeypatch.setattr(store, "collectors", {})

    async def unavailable():
        return None

    monkeypatch.setattr(hyperliquid, "fetch_meta_and_asset_ctxs", unavailable)
    monkeypatch.setattr(hyperliquid, "cache_set", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.readiness.cache_backend_status", lambda: ("fallback", "Test memory cache"))
    for name in ("persist_traders", "persist_liquidations", "persist_positions_from_alerts", "refresh_dashboard"):
        monkeypatch.setattr(store, name, lambda *args: None)
    snapshot = asyncio.run(hyperliquid.collect_market_snapshot())
    assert snapshot["source"] == "unavailable"
    assert store.last_collect_at == NOW
    assert get_readiness(now=NOW).collector.status == "degraded"


def test_partial_whale_collection_preserves_previous_success_time(monkeypatch):
    monkeypatch.setattr(store, "collectors", {})
    store.record_collection("whales", 100, 100)
    success_at = store.collectors["whales"].last_success_at
    store.record_collection("whales", 98, 100)
    state = store.pipeline_status().collectors["whales"]
    assert state.status == "partial"
    assert state.last_success_at == success_at
    assert state.successful == 98
    store.record_collection("whales", 0, 100)
    assert store.collectors["whales"].status == "error"
    assert store.collectors["whales"].last_success_at == success_at


def test_degraded_cycle_does_not_record_paper_decisions(monkeypatch):
    from app.services.paper_portfolio import run_paper_portfolio

    monkeypatch.setattr(store, "collectors", {})
    store.record_collection("whales", 98, 100)
    assert run_paper_portfolio(NOW) is False


def test_public_trades_are_not_collected_as_liquidations(monkeypatch):
    from app.collectors.liquidations import collect_liquidation_events

    monkeypatch.setattr(settings, "use_mock_data", False)
    monkeypatch.setattr(store, "collectors", {})
    monkeypatch.setattr(store, "liquidation_events", [object()])
    assert asyncio.run(collect_liquidation_events()) == []
    assert store.collectors["liquidations"].status == "error"
