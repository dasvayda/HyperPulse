from datetime import datetime, timedelta, timezone

from app.collectors.fills import (
    position_check_line,
    summarize_fills,
)
from app.models.schemas import OpenPosition, PositionSide


def _fill(hours_ago: float, coin: str, side: str, px: float, sz: float, pnl: float = 0.0):
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).timestamp() * 1000
    return {
        "coin": coin,
        "px": str(px),
        "sz": str(sz),
        "side": side,
        "time": ts,
        "closedPnl": str(pnl),
    }


def test_summarize_fills_splits_buy_and_sell():
    raw = [
        _fill(1, "BTC", "B", 100, 10),
        _fill(2, "BTC", "A", 100, 4),
        _fill(3, "ETH", "A", 50, 2),
    ]
    out = summarize_fills(raw)
    assert out.fills == 3
    assert out.buy_usd == 1000
    assert out.sell_usd == 500
    assert out.net_usd == 500
    assert out.top_asset == "BTC"
    btc = next(a for a in out.assets if a.asset == "BTC")
    assert btc.net_usd == 600
    assert out.last_fill_at is not None


def test_summarize_fills_drops_rows_outside_window():
    raw = [_fill(1, "BTC", "B", 100, 1), _fill(30, "BTC", "B", 100, 99)]
    out = summarize_fills(raw, window_hours=24)
    assert out.fills == 1
    assert out.buy_usd == 100


def test_summarize_fills_handles_garbage_rows():
    raw = [{"coin": "BTC"}, None, {"coin": "BTC", "px": "x", "sz": "1", "time": 0}]
    out = summarize_fills(raw)  # type: ignore[arg-type]
    assert out.fills == 0
    assert out.top_asset is None


def test_position_check_adding_and_trimming():
    raw = [_fill(1, "BTC", "B", 100, 10)]
    summary = summarize_fills(raw)
    long_pos = [
        OpenPosition(
            asset="BTC",
            side=PositionSide.LONG,
            size_usd=1_000_000,
            entry_price=100,
            leverage=5,
        )
    ]
    assert position_check_line(summary, long_pos) == "Adding to the open BTC long"

    short_pos = [
        OpenPosition(
            asset="BTC",
            side=PositionSide.SHORT,
            size_usd=1_000_000,
            entry_price=100,
            leverage=5,
        )
    ]
    assert position_check_line(summary, short_pos) == "Trimming the open BTC short"


def test_position_check_without_open_position():
    summary = summarize_fills([_fill(1, "BTC", "A", 100, 10)])
    assert position_check_line(summary, []) == "No open BTC position left after this flow"


def test_position_check_none_when_no_fills():
    assert position_check_line(summarize_fills([]), []) is None
