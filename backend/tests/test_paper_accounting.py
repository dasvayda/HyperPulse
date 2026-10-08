import pytest

from app.db import SessionLocal
from app.models.orm import PaperDecisionRow
from app.services.paper_portfolio import (
    _accrue_funding, _ensure_strategy, _portfolio_values, _rebalance_position,
)
from app.services.store import store
from tests.test_paper_portfolio import AT, _clear


@pytest.mark.parametrize("direction,exit_mark,entry_fill,exit_fill,funding", [
    ("long", 110.0, 100.02, 109.978, -0.21),
    ("short", 90.0, 99.98, 90.018, 0.21),
])
def test_round_trip_nav_includes_costs_once_and_funding_side(
    monkeypatch, direction, exit_mark, entry_fill, exit_fill, funding,
):
    _clear()
    monkeypatch.setattr(store, "market_ticks", {"BTC": {"funding_rate": 0.001}})
    with SessionLocal() as db:
        strategy = _ensure_strategy(db, AT)
        decision = PaperDecisionRow(id="audit", strategy_id=strategy.id, bucket="audit",
                                    asset="BTC", action=direction, mark_price=100, created_at=AT)
        _rebalance_position(db, strategy, decision, 200)
        db.flush()
        opening_fee = 2 * entry_fill * 0.00045
        assert strategy.cash == pytest.approx(1000 - opening_fee)
        nav, gross, upnl = _portfolio_values(db, strategy, {"BTC": 100})
        assert gross == pytest.approx(200)
        assert upnl == pytest.approx(-0.04)
        assert nav == pytest.approx(1000 - opening_fee - 0.04)
        _accrue_funding(db, strategy, {"BTC": 105})
        assert strategy.cumulative_funding == pytest.approx(funding)
        decision.action = "wait"
        decision.mark_price = exit_mark
        _rebalance_position(db, strategy, decision, 0)
        db.flush()
        pnl = 2 * (exit_fill - entry_fill) * (1 if direction == "long" else -1)
        fees = opening_fee + 2 * exit_fill * 0.00045
        assert strategy.realized_pnl == pytest.approx(pnl)
        assert strategy.cumulative_fees == pytest.approx(fees)
        assert strategy.cumulative_slippage == pytest.approx(0.04 + 2 * abs(exit_fill - exit_mark))
        final_nav, gross, upnl = _portfolio_values(db, strategy, {"BTC": exit_mark})
        assert gross == upnl == 0
        assert final_nav == pytest.approx(1000 + pnl - fees + funding)
