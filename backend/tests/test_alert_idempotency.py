import asyncio

from app.db import SessionLocal
from app.models.orm import AlertRow
from app.services import alerts
from app.services.store import store


EVENT_TYPE = "whale_move_entry"
PAYLOAD = {"id": "source-event-1", "trader_address": "0xabc"}
KEY = f"{EVENT_TYPE}:source-event-1"


def _clear() -> None:
    db = SessionLocal()
    try:
        db.query(AlertRow).filter(AlertRow.dedupe_key == KEY).delete()
        db.commit()
    finally:
        db.close()


def test_sent_source_event_is_not_delivered_twice(monkeypatch) -> None:
    _clear()
    monkeypatch.setattr(store, "alerts", [])
    calls: list[str] = []

    async def sent_once(message: str) -> bool:
        calls.append(message)
        return True

    monkeypatch.setattr(alerts, "_send_telegram", sent_once)
    try:
        first = asyncio.run(alerts._dispatch(EVENT_TYPE, "Test", ["Test"], PAYLOAD))
        second = asyncio.run(alerts._dispatch(EVENT_TYPE, "Test", ["Test"], PAYLOAD))

        assert first is not None
        assert second is None
        assert len(calls) == 1
        db = SessionLocal()
        try:
            assert db.query(AlertRow).filter(AlertRow.dedupe_key == KEY).count() == 1
        finally:
            db.close()
    finally:
        _clear()


def test_failed_source_event_reuses_the_same_alert_record(monkeypatch) -> None:
    _clear()
    monkeypatch.setattr(store, "alerts", [])
    outcomes = iter([False, True])

    async def eventually_sent(message: str) -> bool:
        return next(outcomes)

    monkeypatch.setattr(alerts, "_send_telegram", eventually_sent)
    try:
        failed = asyncio.run(alerts._dispatch(EVENT_TYPE, "Test", ["Test"], PAYLOAD))
        sent = asyncio.run(alerts._dispatch(EVENT_TYPE, "Test", ["Test"], PAYLOAD))

        assert failed is not None and failed.status == "failed"
        assert sent is not None and sent.status == "sent"
        assert sent.id == failed.id
        db = SessionLocal()
        try:
            rows = db.query(AlertRow).filter(AlertRow.dedupe_key == KEY).all()
            assert len(rows) == 1
            assert rows[0].status == "sent"
        finally:
            db.close()
    finally:
        _clear()
