import asyncio
from datetime import datetime, timezone

from app.models.schemas import AlertHistoryItem, LiqProximityRow, PositionSide
from app.services.alerts import (
    format_liq_proximity_lines,
    select_liq_proximity_alert,
    send_liq_proximity_alert,
)
from app.services.store import store


ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _row(**overrides) -> LiqProximityRow:
    payload = {
        "rank": 1,
        "trader_address": ADDRESS,
        "trader_alias": "Whale A",
        "asset": "BTC",
        "side": PositionSide.LONG,
        "size_usd": 2_400_000.0,
        "leverage": 10.0,
        "mark_price": 100_000.0,
        "liquidation_px": 98_500.0,
        "distance_pct": 1.5,
        "source": "liquidationPx",
    }
    payload.update(overrides)
    return LiqProximityRow(**payload)


def test_select_alert_uses_actual_liq_price_and_actionable_distance() -> None:
    rows = [
        _row(distance_pct=0.5, source="estimate"),
        _row(distance_pct=6.0),
        _row(distance_pct=3.5, size_usd=100_000.0),
        _row(distance_pct=1.5),
    ]
    selected = select_liq_proximity_alert(rows)
    assert selected is not None
    assert selected.distance_pct == 1.5
    assert selected.source == "liquidationPx"


def test_format_liq_danger_is_retail_readable() -> None:
    title, lines = format_liq_proximity_lines(_row())
    text = "\n".join(lines)
    assert title == "LIQ DANGER · BTC LONG · 0xaaaa…aaaa"
    assert "$2.4M LONG position" in text
    assert "liq $98,500" in text
    assert "1.5% away" in text
    assert "Watch forced selling if BTC falls" in text


def test_same_band_and_wallet_cools_down(monkeypatch) -> None:
    title, _ = format_liq_proximity_lines(_row())
    existing = AlertHistoryItem(
        id="alert-1",
        channel="telegram",
        event_type="liq_proximity",
        title=title,
        message="older distance text",
        status="queued",
        created_at=datetime.now(timezone.utc),
        sent_at=None,
    )
    monkeypatch.setattr(store, "alerts", [existing])
    assert asyncio.run(send_liq_proximity_alert([_row(distance_pct=1.2)])) is None


def test_watch_can_escalate_to_danger(monkeypatch) -> None:
    watch = _row(distance_pct=4.0)
    watch_title, _ = format_liq_proximity_lines(watch)
    existing = AlertHistoryItem(
        id="alert-2",
        channel="telegram",
        event_type="liq_proximity",
        title=watch_title,
        message="watch",
        status="queued",
        created_at=datetime.now(timezone.utc),
        sent_at=None,
    )
    monkeypatch.setattr(store, "alerts", [existing])

    called = []

    async def fake_dispatch(event_type, title, lines, payload):
        called.append((event_type, title, lines, payload))
        return existing

    monkeypatch.setattr("app.services.alerts._dispatch", fake_dispatch)
    result = asyncio.run(send_liq_proximity_alert([_row(distance_pct=1.8)]))
    assert result is existing
    assert called[0][0] == "liq_proximity"
    assert "LIQ DANGER" in called[0][1]


def test_cooled_closest_wallet_does_not_starve_next_wallet(monkeypatch) -> None:
    closest = _row(distance_pct=1.0)
    closest_title, _ = format_liq_proximity_lines(closest)
    existing = AlertHistoryItem(
        id="alert-3",
        channel="telegram",
        event_type="liq_proximity",
        title=closest_title,
        message="already sent",
        status="queued",
        created_at=datetime.now(timezone.utc),
        sent_at=None,
    )
    monkeypatch.setattr(store, "alerts", [existing])
    next_wallet = _row(
        trader_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        trader_alias="Whale B",
        distance_pct=1.4,
    )
    called = []

    async def fake_dispatch(event_type, title, lines, payload):
        called.append((event_type, title, lines, payload))
        return existing

    monkeypatch.setattr("app.services.alerts._dispatch", fake_dispatch)
    result = asyncio.run(send_liq_proximity_alert([closest, next_wallet]))
    assert result is existing
    assert "0xbbbb…bbbb" in called[0][1]
