from datetime import datetime, timedelta, timezone

from app.models.schemas import AlertType, PositionSide, WhaleAlert
from app.services.fresh_entries import classify_size_change, is_fresh_entry
from app.services.liq_windows import pressure_line, rollup_events


def _alert(hours_ago: float, alert_type: AlertType = AlertType.ENTRY) -> WhaleAlert:
    now = datetime.now(timezone.utc)
    return WhaleAlert(
        id="wa-test",
        trader_address="0xabc",
        trader_alias="T",
        asset="BTC",
        side=PositionSide.LONG,
        alert_type=alert_type,
        size_usd=1_000_000,
        leverage=10,
        win_rate=50,
        inferred_strategy="Directional",
        confidence_score=80,
        timestamp=now - timedelta(hours=hours_ago),
    )


def test_fresh_entry_within_24h():
    now = datetime.now(timezone.utc)
    assert is_fresh_entry(_alert(1), now) is True
    assert is_fresh_entry(_alert(30), now) is False
    assert is_fresh_entry(_alert(1, AlertType.EXIT), now) is False


def test_classify_same_side_add():
    kind, delta = classify_size_change(1.0, 2.0, 500_000, 1_200_000, 250_000)
    assert kind == AlertType.ENTRY
    assert delta == 700_000


def test_classify_small_add_ignored():
    kind, delta = classify_size_change(1.0, 1.1, 500_000, 550_000, 250_000)
    assert kind is None
    assert delta is None


def test_classify_flip_and_exit():
    kind, _ = classify_size_change(1.0, -1.0, 500_000, 500_000, 250_000)
    assert kind == AlertType.ENTRY
    kind, delta = classify_size_change(1.0, 0.0, 500_000, 0.0, 250_000)
    assert kind == AlertType.EXIT
    assert delta == -500_000


class _Evt:
    def __init__(self, hours_ago, side, size):
        self.timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        self.side = side
        self.size_usd = size


def test_liq_rollup_and_pressure():
    now = datetime.now(timezone.utc)
    events = [
        _Evt(0.5, "long", 300),
        _Evt(0.2, "short", 100),
        _Evt(3.0, "long", 900),
    ]
    one = rollup_events(events, 1, now)
    four = rollup_events(events, 4, now)
    assert one["long_usd"] == 300
    assert one["short_usd"] == 100
    assert four["long_usd"] == 1200
    assert pressure_line(one) == "long-flush pressure"
    assert pressure_line({"total_usd": 0}) == "sampled liq quiet"
