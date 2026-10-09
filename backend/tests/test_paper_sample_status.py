from datetime import timedelta

from app.db import SessionLocal
from app.models.orm import PaperEquityRow, PaperTradeRow
from app.services.paper_portfolio import _ensure_strategy, get_paper_summary
from app.services.store import store
from tests.test_paper_portfolio import AT, _clear


def test_elapsed_days_and_partial_reductions_do_not_complete_shadow_sample(monkeypatch):
    _clear()
    monkeypatch.setattr(store, "collectors", {})
    with SessionLocal() as db:
        strategy = _ensure_strategy(db, AT - timedelta(days=40))
        for i in range(2):
            db.add(PaperEquityRow(id=f"sample-{i}", strategy_id=strategy.id, bucket=f"h{i}",
                                 cash=1000, nav=1000, created_at=AT + timedelta(hours=i)))
        for i in range(100):
            db.add(PaperTradeRow(id=f"sample-trade-{i}", strategy_id=strategy.id,
                                decision_id="sample", asset="BTC", side="sell",
                                action="close" if i == 0 else "reduce", quantity=1,
                                mark_price=100, fill_price=100, notional_usd=100))
        db.commit()
    summary = get_paper_summary()
    assert summary.closed_trades_count == 100
    assert summary.fully_closed_positions_count == 1
    assert summary.observed_hour_buckets == 2
    assert summary.minimum_sample_met is False
    assert summary.evaluation_paused is True
