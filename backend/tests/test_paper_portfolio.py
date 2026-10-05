from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models.orm import (
    MarketSnapshotRow,
    PaperDecisionRow,
    PaperEquityRow,
    PaperPositionRow,
    PaperRosterRow,
    PaperStrategyRow,
    PaperTradeRow,
    WhaleFlowRow,
)
from app.models.schemas import PositionSide, SmartMoneyRank, WhalePosition
from app.services.paper_portfolio import (
    STRATEGY_ID,
    get_paper_summary,
    record_whale_flows,
    run_paper_portfolio,
)
from app.services.store import store


AT = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def _clear() -> None:
    db = SessionLocal()
    try:
        for model in (
            PaperTradeRow,
            PaperEquityRow,
            PaperDecisionRow,
            PaperPositionRow,
            PaperRosterRow,
            WhaleFlowRow,
            PaperStrategyRow,
            MarketSnapshotRow,
        ):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()


def _rank(index: int) -> SmartMoneyRank:
    address = f"0x{index:040x}"
    return SmartMoneyRank(
        address=address,
        alias=f"Whale {index}",
        rank=index,
        smart_money_score=100 - index,
        pnl_usd=1_000_000 - index,
        account_value_usd=10_000_000 - index,
        pnl_change_pct=10.0,
        strategy_tags=[],
        risk_score=10.0,
        momentum_score=80.0,
        consistency_score=80.0,
        sparkline=[1.0, 2.0],
    )


def _seed_long_case() -> None:
    store.rankings = [_rank(i) for i in range(1, 6)]
    store.whale_positions = [
        WhalePosition(
            trader_address=f"0x{i:040x}",
            asset="BTC",
            side=PositionSide.LONG,
            size_usd=1_000_000 - i * 10_000,
            entry_price=100.0,
            leverage=1.0,
        )
        for i in range(1, 6)
    ]
    store.market_ticks = {"BTC": {"funding_rate": 0.0}}
    db = SessionLocal()
    try:
        for hour, price in [(8, 96.0), (9, 97.0), (10, 98.0), (11, 99.0), (12, 101.0), (13, 103.0)]:
            db.add(
                MarketSnapshotRow(
                    asset="BTC",
                    mark_price=price,
                    open_interest=1.0,
                    funding_rate=0.0,
                    day_volume_usd=1_000_000.0,
                    timestamp=AT.replace(hour=hour),
                )
            )
        for asset, price in (("ETH", 4_000.0), ("SOL", 200.0)):
            for hour in (8, 11, 12, 13):
                db.add(
                    MarketSnapshotRow(
                        asset=asset,
                        mark_price=price,
                        open_interest=1.0,
                        funding_rate=0.0,
                        day_volume_usd=1_000_000.0,
                        timestamp=AT.replace(hour=hour),
                    )
                )
        for flow_at in (AT - timedelta(minutes=30), AT + timedelta(minutes=30)):
            for i in range(1, 4):
                db.add(
                    WhaleFlowRow(
                        id=f"flow-{flow_at.hour}-{i}",
                        trader_address=f"0x{i:040x}",
                        asset="BTC",
                        delta_usd=100_000.0 + i,
                        previous_usd=500_000.0,
                        current_usd=600_000.0 + i,
                        created_at=flow_at,
                    )
                )
        db.commit()
    finally:
        db.close()


def test_top5_strategy_opens_after_two_confirmations() -> None:
    _clear()
    _seed_long_case()

    assert run_paper_portfolio(AT) is True
    first = get_paper_summary()
    assert first.trades_count == 0

    assert run_paper_portfolio(AT + timedelta(hours=1)) is True
    assert run_paper_portfolio(AT + timedelta(hours=1, minutes=5)) is False
    summary = get_paper_summary()

    assert summary.strategy_id == STRATEGY_ID
    assert summary.trades_count == 1
    assert len(summary.current_positions) == 1
    assert summary.current_positions[0].asset == "BTC"
    assert summary.current_positions[0].direction == "long"
    assert 390.0 <= summary.current_positions[0].notional_usd <= 410.0
    assert summary.cumulative_fees > 0
    assert summary.cumulative_slippage > 0
    assert summary.last_decisions[0]["action"] in {"long", "wait"}


def test_flow_recorder_uses_signed_position_delta_and_observed_wallets() -> None:
    _clear()
    a = "0x" + "a" * 40
    b = "0x" + "b" * 40
    previous = [
        WhalePosition(
            trader_address=a,
            asset="BTC",
            side=PositionSide.LONG,
            size_usd=100.0,
            entry_price=100.0,
            leverage=1.0,
        ),
        WhalePosition(
            trader_address=b,
            asset="BTC",
            side=PositionSide.SHORT,
            size_usd=200.0,
            entry_price=100.0,
            leverage=1.0,
        ),
    ]
    current = [
        WhalePosition(
            trader_address=a,
            asset="BTC",
            side=PositionSide.SHORT,
            size_usd=50.0,
            entry_price=100.0,
            leverage=1.0,
        )
    ]

    count = record_whale_flows(previous, current, observed_addresses={a}, at=AT)
    assert count == 1
    db = SessionLocal()
    try:
        rows = db.query(WhaleFlowRow).all()
        assert len(rows) == 1
        assert rows[0].trader_address == a
        assert rows[0].delta_usd == -150.0
    finally:
        db.close()
