import asyncio
import hashlib
import json
import sqlite3
from datetime import timedelta

import pytest

from app.config import settings
from app.db import SessionLocal
from app.models.orm import LiquidationCoverageRow, LiquidationQuarantineRow, VerifiedLiquidationRow
from app.services import verified_liquidations as service

WALLET = "0x" + "a" * 40


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(settings, "verified_liquidations_enabled", True)
    monkeypatch.setattr(settings, "liquidation_watch_addresses", WALLET)
    monkeypatch.setattr(settings, "liquidation_other_ws_users", 0)
    with SessionLocal() as db:
        for model in (LiquidationCoverageRow, LiquidationQuarantineRow, VerifiedLiquidationRow):
            db.query(model).delete()
        db.commit()


def fill(**overrides):
    return {"coin": "BTC", "px": "100", "sz": "2", "startPosition": "3", "side": "A",
            "time": int(service.utcnow().timestamp() * 1000), "tid": 123,
            "hash": "0x" + "b" * 64,
            "liquidation": {"liquidatedUser": WALLET, "markPx": 99, "method": "market"}, **overrides}


@pytest.mark.parametrize("method", ["market", "backstop"])
def test_fill_direction_notional_and_duplicate(method):
    raw = fill(liquidation={"liquidatedUser": WALLET, "markPx": 99, "method": method})
    assert service.ingest(WALLET, [raw, raw]) == (1, 0)
    with SessionLocal() as db:
        row = db.query(VerifiedLiquidationRow).one()
        assert row.side == "long" and row.size_usd == 200 and row.price == 100
        assert json.loads(row.raw_json)["fill"]["liquidation"]["markPx"] == 99
    short = service.normalize_fill(WALLET, fill(side="B", startPosition="-3"))
    assert short["side"] == "short"


@pytest.mark.parametrize("changes", [
    {"px": "nan"}, {"px": True}, {"sz": "inf"}, {"sz": "4"}, {"px": "0"}, {"side": "B"},
    {"startPosition": "0"}, {"tid": True}, {"time": -1}, {"hash": "bad"},
    {"liquidation": {"markPx": 99, "method": "market"}},
    {"liquidation": {"liquidatedUser": "0x" + "c" * 40, "markPx": 99, "method": "market"}},
])
def test_ambiguous_or_invalid_fills_quarantined(changes):
    assert service.ingest(WALLET, [fill(**changes)]) == (0, 1)
    with SessionLocal() as db:
        assert db.query(VerifiedLiquidationRow).count() == 0
        assert db.query(LiquidationQuarantineRow).count() == 1


def test_ordinary_trade_is_not_a_liquidation():
    raw = fill()
    del raw["liquidation"]
    assert service.ingest(WALLET, [raw]) == (0, 0)


def test_coverage_zero_null_gaps_restart_and_roster(monkeypatch):
    now = service.utcnow()
    monkeypatch.setattr(service, "utcnow", lambda: now)
    assert service.summary()["long_usd"] is None
    key = service.coverage_start([WALLET])
    assert service.summary()["status"] == "partial"
    with SessionLocal() as db:
        row = db.get(LiquidationCoverageRow, key)
        row.started_at = now - timedelta(hours=2)
        db.commit()
    assert service.summary()["long_usd"] == 0
    assert service.summary()["paper_compatible"] is False
    service.coverage_touch(key, end="disconnect")
    monkeypatch.setattr(service, "utcnow", lambda: now + timedelta(minutes=5))
    assert service.summary()["long_usd"] is None
    service.coverage_start([WALLET])
    assert service.summary()["status"] == "partial"
    assert service.summary()["gap"] is True
    monkeypatch.setattr(settings, "liquidation_watch_addresses", "0x" + "c" * 40)
    assert service.summary()["status"] == "unavailable"


def test_ws_user_budget(monkeypatch):
    monkeypatch.setattr(settings, "liquidation_other_ws_users", 10)
    with pytest.raises(ValueError):
        service.watch_addresses()


def test_out_of_order_events_and_disabled_feed_do_not_fake_completeness(monkeypatch):
    now = service.utcnow()
    older = fill(time=int((now - timedelta(minutes=20)).timestamp() * 1000), tid=124)
    newer = fill(time=int((now - timedelta(minutes=5)).timestamp() * 1000))
    assert service.ingest(WALLET, [newer, older, newer]) == (2, 0)
    assert service.summary()["long_usd"] is None
    assert service.summary()["observed_long_usd"] == 400
    monkeypatch.setattr(settings, "verified_liquidations_enabled", False)
    assert service.summary()["events"] == 0
    assert service.summary()["status"] == "unavailable"


def test_live_paper_cannot_resume_when_collector_is_marked_ok(monkeypatch):
    from app.services.store import store
    from app.services.paper_portfolio import run_paper_portfolio
    monkeypatch.setattr(settings, "use_mock_data", False)
    monkeypatch.setattr(store, "collectors", {})
    assert run_paper_portfolio() is False


def test_legacy_audit_is_read_only(tmp_path):
    from scripts.audit_legacy_liquidations import audit
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE liquidations (timestamp TEXT, asset TEXT, size_usd REAL, tx_hash TEXT)")
        db.execute("INSERT INTO liquidations VALUES ('2026-10-01', 'BTC', 123, 'legacy-hash')")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = audit(path)
    assert result["verified"] is False
    assert result["groups"][0]["with_tx_hash"] == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_stream_cancellation_closes_coverage_without_rest(monkeypatch):
    from app.collectors import liquidation_stream
    import websockets.asyncio.client

    calls = []

    class Socket:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def send(self, body): calls.append(json.loads(body))
        async def recv(self):
            if len(calls) == 1:
                calls.append("received")
                return json.dumps({"channel": "userFills", "data": {"user": WALLET, "isSnapshot": True, "fills": []}})
            raise asyncio.CancelledError()

    monkeypatch.setattr(websockets.asyncio.client, "connect", lambda *a, **kw: Socket())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(liquidation_stream.run_liquidation_stream())
    assert calls[0]["subscription"]["aggregateByTime"] is False
    with SessionLocal() as db:
        row = db.query(LiquidationCoverageRow).one()
        assert row.ended_at is not None
