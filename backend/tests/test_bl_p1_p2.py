from app.models.schemas import OpenPosition, PositionSide
from app.services.copy_check import compute_copy_verdict
from app.services.liq_proximity import (
    estimate_liquidation_px,
    liq_distance_pct,
    list_liq_proximity,
)
from app.services.cohort_bias import _long_pct
from app.models.schemas import WhalePosition
from app.services.market_pulse import _delta_pct


def test_liq_distance_long_and_short():
    assert liq_distance_pct(side="long", mark=100, liquidation_px=90) == 10.0
    assert liq_distance_pct(side="short", mark=100, liquidation_px=110) == 10.0
    assert liq_distance_pct(side="long", mark=90, liquidation_px=100) == -11.11
    assert liq_distance_pct(side="long", mark=0, liquidation_px=90) is None


def test_estimate_liquidation_px():
    long_px = estimate_liquidation_px(side="long", entry_price=100, leverage=10)
    short_px = estimate_liquidation_px(side="short", entry_price=100, leverage=10)
    assert long_px is not None and long_px < 100
    assert short_px is not None and short_px > 100


def test_list_liq_proximity_sorts_closest_first():
    positions = [
        WhalePosition(
            trader_address="0xaaa",
            asset="BTC",
            side=PositionSide.LONG,
            size_usd=1_000_000,
            entry_price=100,
            leverage=10,
            liquidation_px=80,
        ),
        WhalePosition(
            trader_address="0xbbb",
            asset="ETH",
            side=PositionSide.LONG,
            size_usd=500_000,
            entry_price=100,
            leverage=10,
            liquidation_px=95,
        ),
    ]
    rows = list_liq_proximity(
        positions,
        marks={"BTC": 100.0, "ETH": 100.0},
        traders_by_addr={"0xaaa": "A", "0xbbb": "B"},
        limit=5,
    )
    assert len(rows) == 2
    assert rows[0].trader_alias == "B"
    assert rows[0].distance_pct < rows[1].distance_pct
    assert rows[0].source == "liquidationPx"


def test_copy_verdict_watch_caution_skip():
    watch = compute_copy_verdict(
        smart_money_score=72,
        open_roi_pct=8.0,
        open_unrealized_pnl_usd=50_000,
        max_leverage=8,
        risk_score=40,
        inference_confidence=70,
    )
    assert watch.verdict == "watch"

    caution = compute_copy_verdict(
        smart_money_score=45,
        open_roi_pct=-5.0,
        open_unrealized_pnl_usd=-10_000,
        max_leverage=18,
        risk_score=55,
        inference_confidence=40,
    )
    assert caution.verdict == "caution"

    skip = compute_copy_verdict(
        smart_money_score=80,
        open_roi_pct=5.0,
        open_unrealized_pnl_usd=1_000,
        max_leverage=30,
        risk_score=40,
        inference_confidence=80,
    )
    assert skip.verdict == "skip"
    assert any("leverage" in r.lower() for r in skip.reasons)


def test_copy_verdict_from_open_positions():
    positions = [
        OpenPosition(
            asset="BTC",
            side=PositionSide.LONG,
            size_usd=100_000,
            entry_price=50_000,
            leverage=5,
            roi_pct=10.0,
            unrealized_pnl_usd=5_000,
        )
    ]
    out = compute_copy_verdict(
        smart_money_score=65,
        open_roi_pct=None,
        open_unrealized_pnl_usd=None,
        max_leverage=None,
        risk_score=40,
        inference_confidence=60,
        open_positions=positions,
    )
    assert out.verdict == "watch"


def test_long_pct_helper():
    positions = [
        WhalePosition(
            trader_address="0x1",
            asset="BTC",
            side=PositionSide.LONG,
            size_usd=70,
            entry_price=1,
            leverage=5,
        ),
        WhalePosition(
            trader_address="0x2",
            asset="BTC",
            side=PositionSide.SHORT,
            size_usd=30,
            entry_price=1,
            leverage=5,
        ),
    ]
    pct, long_usd, short_usd, whales = _long_pct(positions)
    assert pct == 70.0
    assert long_usd == 70
    assert short_usd == 30
    assert whales == 2


def test_delta_pct():
    assert _delta_pct(110, 100) == 10.0
    assert _delta_pct(90, 100) == -10.0
    assert _delta_pct(100, None) is None
    assert _delta_pct(100, 0) is None
