import asyncio
from threading import Event
from types import SimpleNamespace

from sqlalchemy import text

from app.collectors import scheduler
from app.db import engine, init_db
from app.models.schemas import PositionSide
from app.services import store as store_module
from app.services.store import store


def test_live_prices_shared_without_database_reads(monkeypatch):
    positions = [SimpleNamespace(asset="BTC", side=PositionSide.LONG,
                                 entry_price=100, size_usd=110, leverage=2)]
    monkeypatch.setattr(store, "whale_positions", positions)
    monkeypatch.setattr(store, "whale_positions_by_trader", {"wallet": positions})
    monkeypatch.setattr(store, "market_ticks", {"BTC": {"mark_price": 110}})
    calls = []
    monkeypatch.setattr(store_module, "_latest_mark_prices", lambda assets: calls.append(set(assets)) or {})
    marks = store.current_mark_prices()
    for _ in range(100):
        roi, pnl = store.summarize_open_pnl("wallet", marks=marks)
        assert round(roi, 2) == 18.18
        assert round(pnl, 3) == 10
    assert calls == [set()]


def test_missing_or_invalid_live_prices_fetch_once(monkeypatch):
    monkeypatch.setattr(store, "whale_positions", [SimpleNamespace(asset="BTC"), SimpleNamespace(asset="ETH")])
    monkeypatch.setattr(store, "market_ticks", {"BTC": {"mark_price": float("nan")}, "ETH": {"mark_price": 200}})
    calls = []
    monkeypatch.setattr(store_module, "_latest_mark_prices", lambda assets: calls.append(set(assets)) or {"BTC": 100})
    assert store.current_mark_prices() == {"BTC": 100, "ETH": 200}
    assert calls == [{"BTC"}]


def test_ranking_does_not_block_event_loop(monkeypatch):
    started, release = Event(), Event()

    def slow_ranking():
        started.set()
        assert release.wait(3)
        return []

    monkeypatch.setattr(scheduler, "run_ranking_pipeline", slow_ranking)

    async def probe():
        task = asyncio.create_task(scheduler._ranking_cycle())
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set()
            assert not task.done()
        finally:
            release.set()
            await task

    asyncio.run(probe())


def test_existing_sqlite_receives_latest_price_index():
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_market_snapshots_asset_timestamp"))
    init_db()
    with engine.connect() as conn:
        plan = conn.execute(text("EXPLAIN QUERY PLAN SELECT mark_price FROM market_snapshots WHERE asset='BTC' ORDER BY timestamp DESC LIMIT 1")).fetchall()
    details = " ".join(str(row) for row in plan)
    assert "ix_market_snapshots_asset_timestamp" in details
    assert "TEMP B-TREE" not in details
