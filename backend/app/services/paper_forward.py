"""Forward-only simulated execution. Historical prices never create new signals."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.models.orm import (MarketSnapshotRow, PaperDecisionRow, PaperEquityRow, PaperFundingPaymentRow,
                            PaperFundingRateRow, PaperOrderRow, PaperPositionRow, PaperRunStateRow, WhaleFlowRow)
from app.services.store import store


def aware(at):
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at


class InputUnavailable(Exception):
    pass


def input_reason(at: datetime, db) -> str | None:
    from app.services import paper_portfolio as p
    if not settings.paper_portfolio_enabled:
        return "Paper evaluation is disabled"
    for name in ("market", "whales"):
        state = store.collectors.get(name)
        if not state or state.status != "ok" or not state.last_success_at:
            return f"Waiting for complete {name} collection"
        age = (at - aware(state.last_success_at)).total_seconds()
        if not 0 <= age <= 600:
            return f"Waiting for fresh {name} collection"
    if len(p.select_smart_money_ranks(size=15)) < 5:
        return "Waiting for five ranked wallets"
    for asset in p.ASSETS:
        for hours in (0, 1, 4):
            target = at - timedelta(hours=hours)
            snap = p._snapshot_at_or_before(db, asset, target)
            if not snap or not 0 <= (target - aware(snap.timestamp)).total_seconds() <= 600 or not math.isfinite(snap.mark_price) or snap.mark_price <= 0 or not math.isfinite(snap.funding_rate):
                return f"Waiting for {asset} price history ({hours}h)"
    return None


def settle_funding(db, strategy, state, until):
    """One row per held asset/hour. Rate is actual; notional uses sampled mark."""
    from app.services import paper_portfolio as p
    hour = aware(state.funding_through).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while hour <= until:
        for pos in db.query(PaperPositionRow).filter_by(strategy_id=strategy.id).all():
            if aware(pos.opened_at) >= hour:
                continue
            rate = db.get(PaperFundingRateRow, f"{pos.asset}:{int(hour.timestamp())}")
            snap = p._snapshot_at_or_before(db, pos.asset, hour)
            if not rate or not math.isfinite(rate.rate) or not snap or not math.isfinite(snap.mark_price) or (hour - aware(snap.timestamp)).total_seconds() > 600 or snap.mark_price <= 0:
                raise InputUnavailable(f"Waiting for {pos.asset} funding/mark at {hour.isoformat()}")
            key = f"{strategy.id}:{pos.asset}:{int(hour.timestamp())}"
            if not db.get(PaperFundingPaymentRow, key):
                amount = (-1 if pos.direction == "long" else 1) * pos.quantity * snap.mark_price * rate.rate
                db.add(PaperFundingPaymentRow(id=key, strategy_id=strategy.id, asset=pos.asset, funded_at=hour,
                                             rate=rate.rate, quantity=pos.quantity, mark_price=snap.mark_price, amount=amount))
                strategy.cash += amount
                strategy.cumulative_funding += amount
                db.flush()
        hour += timedelta(hours=1)
    state.funding_through = until


def record_equity(db, strategy, at, marks):
    from app.services import paper_portfolio as p
    nav, gross, upnl = p._portfolio_values(db, strategy, marks)
    strategy.peak_nav = max(strategy.peak_nav, nav)
    strategy.updated_at = at
    bucket = p._hour_bucket(at)
    key = f"{strategy.id}:{bucket}"
    row = db.get(PaperEquityRow, key)
    if row is None:
        row = PaperEquityRow(id=key, strategy_id=strategy.id, bucket=bucket, cash=strategy.cash, nav=nav)
        db.add(row)
    # Latest valuation for this hour; signal decisions remain immutable.
    row.cash, row.nav, row.gross_exposure_usd = strategy.cash, nav, gross
    row.unrealized_pnl_usd, row.realized_pnl_usd = upnl, strategy.realized_pnl
    row.return_pct = (nav / strategy.initial_cash - 1) * 100
    row.benchmark_nav = strategy.initial_cash * marks["BTC"] / strategy.benchmark_start_price if strategy.benchmark_start_price else None
    drawdown = (nav / strategy.peak_nav - 1) * 100 if strategy.peak_nav > 0 else 0
    row.drawdown_pct = min(row.drawdown_pct or 0, drawdown)
    row.cumulative_fees, row.cumulative_slippage, row.cumulative_funding = strategy.cumulative_fees, strategy.cumulative_slippage, strategy.cumulative_funding
    row.created_at = at


def execute_pending(db, strategy, state, at):
    from app.services import paper_portfolio as p
    orders = db.query(PaperOrderRow).filter_by(strategy_id=strategy.id, status="pending").order_by(PaperOrderRow.created_at).all()
    for order in orders:
        quotes = {}
        for asset in p.ASSETS:
            quote = db.query(MarketSnapshotRow).filter(MarketSnapshotRow.asset == asset,
                MarketSnapshotRow.timestamp > order.created_at, MarketSnapshotRow.timestamp <= min(at, aware(order.expires_at))).order_by(MarketSnapshotRow.timestamp, MarketSnapshotRow.id).first()
            if quote and math.isfinite(quote.mark_price) and quote.mark_price > 0:
                quotes[asset] = quote
        if len(quotes) != len(p.ASSETS):
            if at >= aware(order.expires_at):
                order.status = "expired"
            continue
        executed_at = max(aware(q.timestamp) for q in quotes.values())
        if executed_at < aware(state.funding_through):
            order.status = "expired"
            continue
        settle_funding(db, strategy, state, executed_at)
        marks = {a: q.mark_price for a, q in quotes.items()}
        nav, _, _ = p._portfolio_values(db, strategy, marks)
        decisions = db.query(PaperDecisionRow).filter_by(strategy_id=strategy.id, bucket=order.bucket).all()
        total = sum(max(0, decision.target_weight) for decision in decisions)
        scale = min(1, p.CONFIG["max_gross_weight"] / total) if total > 0 else 1
        for decision in decisions:
            # Execute a copy; never replace the recorded signal price or timestamp.
            execution = PaperDecisionRow(id=decision.id, asset=decision.asset, action=decision.action,
                                         mark_price=marks[decision.asset], created_at=executed_at)
            p._rebalance_position(db, strategy, execution, max(0, nav) * min(p.CONFIG["max_asset_weight"], decision.target_weight * scale))
        db.flush()
        order.status, order.executed_at = "filled", executed_at
        order.execution_json = json.dumps({a: {"snapshot_id": q.id, "price": q.mark_price, "as_of": aware(q.timestamp).isoformat()} for a, q in quotes.items()})


def run_forward(at=None):
    from app.services import paper_portfolio as p
    at = aware(at or p._utcnow())
    with store._lock, SessionLocal() as db:
        try:
            if db.bind.dialect.name == "sqlite":
                db.execute(text("BEGIN IMMEDIATE"))
            strategy = p._ensure_strategy(db, at)
            # Serialize scheduled and manually triggered evaluations on PostgreSQL.
            db.query(type(strategy)).filter_by(id=strategy.id).with_for_update().one()
            state = db.get(PaperRunStateRow, strategy.id)
            if state is None:
                state = PaperRunStateRow(strategy_id=strategy.id, funding_through=at, checked_at=at)
                db.add(state)
                db.flush()
            if at < aware(state.checked_at):
                return False
            # Expiry is bookkeeping, independent of collector availability.
            for expired in db.query(PaperOrderRow).filter(PaperOrderRow.strategy_id == strategy.id,
                    PaperOrderRow.status == "pending", PaperOrderRow.expires_at < at).all():
                expired.status = "expired"
            reason = input_reason(at, db)
            if reason:
                state.checked_at, state.pause_reason = at, reason
                db.commit()
                return False
            execute_pending(db, strategy, state, at)
            settle_funding(db, strategy, state, at)
            marks = p._marks(db, at)
            if strategy.benchmark_start_price is None:
                strategy.benchmark_start_price = marks["BTC"]
            bucket = p._hour_bucket(at)
            is_new = db.query(PaperOrderRow).filter_by(strategy_id=strategy.id, bucket=bucket).first() is None
            if is_new:
                roster = p._daily_roster(db, at)
                inputs = {"positions": [row.model_dump(mode="json") for row in store.whale_positions],
                          "market": {a: [{"price": row.mark_price, "funding_rate": row.funding_rate,
                                          "snapshot_id": row.id, "as_of": aware(row.timestamp).isoformat()}
                                         for hours in (0, 1, 4) if (row := p._snapshot_at_or_before(db, a, at - timedelta(hours=hours)))] for a in p.ASSETS},
                          "flow": [{"id": row.id, "wallet": row.trader_address, "asset": row.asset,
                                    "previous_usd": row.previous_usd, "current_usd": row.current_usd,
                                    "delta_usd": row.delta_usd, "as_of": aware(row.created_at).isoformat()}
                                   for row in db.query(WhaleFlowRow).filter(WhaleFlowRow.created_at > at - timedelta(hours=1), WhaleFlowRow.created_at <= at).all()]}
                for asset in p.ASSETS:
                    position, long_pct = p._position_consensus(asset, roster)
                    flow, flow_pct = p._flow_consensus(db, asset, at)
                    trend, r1, r4, latest = p._market_trend(db, asset, at)
                    raw, weight, reason = p._raw_decision(position, flow, trend)
                    funding = latest.funding_rate
                    reduced = (raw == "long" and funding > p.CONFIG["extreme_funding_rate"]) or (raw == "short" and funding < -p.CONFIG["extreme_funding_rate"])
                    if reduced:
                        weight /= 2
                    previous = db.query(PaperDecisionRow).filter_by(strategy_id=strategy.id, asset=asset).order_by(PaperDecisionRow.created_at.desc()).first()
                    confirmed = previous is not None and previous.bucket == p._hour_bucket(at - timedelta(hours=1)) and previous.raw_action == raw
                    current = db.get(PaperPositionRow, f"{strategy.id}:{asset}")
                    nav, _, _ = p._portfolio_values(db, strategy, marks)
                    action = raw if confirmed else current.direction if current else "wait"
                    target = weight if confirmed else min(p.CONFIG["max_asset_weight"], current.quantity * marks[asset] / nav) if current and nav > 0 else 0
                    db.add(PaperDecisionRow(id=f"{strategy.id}:{bucket}:{asset}", strategy_id=strategy.id, bucket=bucket,
                        asset=asset, roster_json=json.dumps(roster), position_signal=position, position_long_pct=long_pct,
                        flow_signal=flow, flow_long_pct=flow_pct, trend=trend, return_1h_pct=r1, return_4h_pct=r4,
                        raw_action=raw, action=action, target_weight=target,
                        risk_json=json.dumps({"inputs": inputs, "funding_rate": funding, "funding_reduced": reduced, "liquidation_filter": False}),
                        reason=reason + ("; awaiting second hourly confirmation" if not confirmed else ""), mark_price=marks[asset], created_at=at))
                db.add(PaperOrderRow(id=f"{strategy.id}:{bucket}", strategy_id=strategy.id, bucket=bucket, status="pending",
                                    created_at=at, expires_at=at + timedelta(seconds=p.CONFIG["order_expiry_sec"])))
            record_equity(db, strategy, at, marks)
            state.checked_at, state.pause_reason = at, None
            db.commit()
            return is_new
        except InputUnavailable as exc:
            db.rollback()
            state = db.get(PaperRunStateRow, p.STRATEGY_ID)
            if state:
                state.checked_at, state.pause_reason = at, str(exc)
                db.commit()
            return False
