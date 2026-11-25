import asyncio
import json
from datetime import timedelta

import pytest

from app.config import settings
from app.db import SessionLocal
from app.models.orm import (MarketSnapshotRow, PaperDecisionRow, PaperOrderRow, PaperPositionRow,
                            PaperStrategyRow, PaperFundingPaymentRow, PaperFundingRateRow, PaperRunStateRow)
from app.services import paper_portfolio as p
from app.services.paper_forward import settle_funding, InputUnavailable
from app.services.store import store
from tests.test_paper_portfolio import AT, _clear, _seed_long_case, healthy


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    _clear()
    for attr in ("collectors", "market_ticks", "whale_observed_at"):
        monkeypatch.setattr(store, attr, {})
    for attr in ("rankings", "whale_positions", "traders"):
        monkeypatch.setattr(store, attr, [])
    monkeypatch.setattr(settings, "use_mock_data", False)
    monkeypatch.setattr(settings, "paper_portfolio_enabled", True)
    monkeypatch.setattr(p, "_utcnow", lambda: AT)
    _seed_long_case()


def quote(at, btc=104):
    with SessionLocal() as db:
        for asset, price in (("BTC", btc), ("ETH", 4000), ("SOL", 200)):
            db.add(MarketSnapshotRow(asset=asset, mark_price=price, funding_rate=0, timestamp=at))
        db.commit()


def signal():
    healthy(AT)
    assert p.run_paper_portfolio(AT)
    later = AT + timedelta(hours=1)
    healthy(later)
    assert p.run_paper_portfolio(later)
    return later


def test_live_mode_ignores_liquidation_failure_and_preserves_v1():
    with SessionLocal() as db:
        db.add(PaperStrategyRow(id="top5_whale_trend_v1", version="1.0", config_hash="frozen", cash=1234))
        db.commit()
    healthy(AT)
    store.collectors["liquidations"] = store.collectors["market"].model_copy(update={"status": "error"})
    assert p.run_paper_portfolio(AT)
    with SessionLocal() as db:
        assert db.get(PaperStrategyRow, "top5_whale_trend_v1").cash == 1234
        assert db.get(PaperStrategyRow, p.STRATEGY_ID).version == "2.0"
        assert len(db.query(PaperDecisionRow).all()) == 3


def test_post_signal_price_and_restart_are_idempotent():
    later = signal()
    assert p.get_trades() == []
    observed = later + timedelta(minutes=1)
    quote(observed, btc=110)
    healthy(observed)
    p.run_paper_portfolio(observed)
    trades = p.get_trades()
    assert len(trades) == 1 and trades[0].mark_price == 110
    assert trades[0].fill_price > 110
    p.run_paper_portfolio(observed)  # New session, no repeated order/fee.
    assert len(p.get_trades()) == 1
    with SessionLocal() as db:
        order = db.get(PaperOrderRow, f"{p.STRATEGY_ID}:{p._hour_bucket(later)}")
        assert order.status == "filled"
        source = db.query(PaperDecisionRow).filter_by(bucket=order.bucket, asset="BTC").one()
        assert source.mark_price == 103  # recorded decision price never overwritten
        assert json.loads(source.risk_json)["liquidation_filter"] is False


def test_missing_follow_up_quote_expires_instead_of_filling_at_signal():
    later = signal()
    expired = later + timedelta(minutes=11)
    quote(expired)
    healthy(expired)
    p.run_paper_portfolio(expired)
    assert p.get_trades() == []
    with SessionLocal() as db:
        assert db.get(PaperOrderRow, f"{p.STRATEGY_ID}:{p._hour_bucket(later)}").status == "expired"


def test_missing_funding_rolls_back_and_retries_once_available(monkeypatch):
    later = signal()
    opened = later + timedelta(minutes=1)
    quote(opened)
    healthy(opened)
    p.run_paper_portfolio(opened)
    hour = later + timedelta(hours=1)
    quote(hour, btc=105)
    healthy(hour)
    monkeypatch.setattr(p, "_utcnow", lambda: hour)
    assert p.run_paper_portfolio(hour) is False
    assert "funding/mark" in p.get_paper_summary().pause_reason
    with SessionLocal() as db:
        assert db.query(PaperFundingPaymentRow).count() == 0
        assert db.query(PaperOrderRow).filter_by(bucket=p._hour_bucket(hour)).count() == 0
    with SessionLocal() as db:
        strategy = db.get(PaperStrategyRow, p.STRATEGY_ID)
        state = db.get(PaperRunStateRow, p.STRATEGY_ID)
        before = strategy.cash
        with pytest.raises(InputUnavailable): settle_funding(db, strategy, state, hour)
        db.rollback()
        db.add(PaperFundingRateRow(id=f"BTC:{int(hour.timestamp())}", asset="BTC", funded_at=hour, rate=0.001))
        db.commit()
    healthy(hour)
    # Need 10:00 price for the 4h trend at 14:00; the fixture already has it.
    assert p.run_paper_portfolio(hour)
    assert not p.run_paper_portfolio(hour)
    with SessionLocal() as db:
        payments = db.query(PaperFundingPaymentRow).all()
        assert len(payments) == 1 and payments[0].amount < 0
        assert db.get(PaperStrategyRow, p.STRATEGY_ID).cash == pytest.approx(before + payments[0].amount)


def test_missing_core_data_pauses_but_no_unrelated_collector_is_required():
    healthy(AT)
    store.collectors["whales"].status = "partial"
    assert not p.run_paper_portfolio(AT)
    summary = p.get_paper_summary()
    assert summary.evaluation_paused and "whales" in summary.pause_reason


def test_gap_in_evaluations_does_not_count_as_second_confirmation():
    healthy(AT)
    assert p.run_paper_portfolio(AT)
    later = AT + timedelta(hours=2)
    quote(later)
    healthy(later)
    assert p.run_paper_portfolio(later)
    with SessionLocal() as db:
        decision = db.query(PaperDecisionRow).filter_by(bucket=p._hour_bucket(later), asset="BTC").one()
        assert decision.raw_action == "long"
        assert decision.action == "wait" and decision.target_weight == 0


def test_historical_rates_collector_is_bounded_validated_and_deduplicated(monkeypatch):
    from app.collectors import paper_funding
    calls = []
    monkeypatch.setattr(paper_funding, "_last_attempt", None)
    async def history(request):
        calls.append(request)
        return [{"coin": request["coin"], "time": int(AT.timestamp() * 1000), "fundingRate": "-0.001"}]
    monkeypatch.setattr(paper_funding, "info", history)
    asyncio.run(paper_funding.collect_paper_funding(AT))
    asyncio.run(paper_funding.collect_paper_funding(AT))
    assert len(calls) == 3
    with SessionLocal() as db:
        assert db.query(PaperFundingRateRow).count() == 3
    asyncio.run(paper_funding.collect_paper_funding(AT + timedelta(minutes=1)))
    with SessionLocal() as db:
        assert db.query(PaperFundingRateRow).count() == 3
