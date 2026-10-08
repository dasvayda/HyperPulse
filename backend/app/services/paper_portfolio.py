from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.orm import (
    LiquidationRow,
    MarketSnapshotRow,
    PaperDecisionRow,
    PaperEquityRow,
    PaperPositionRow,
    PaperRosterRow,
    PaperStrategyRow,
    PaperTradeRow,
    WhaleFlowRow,
)
from app.models.schemas import (
    PaperEquityPoint,
    PaperPortfolioPosition,
    PaperPortfolioSummary,
    PaperPortfolioTrade,
    PaperStrategyDetail,
    WhalePosition,
)
from app.services.ranking import select_smart_money_ranks
from app.services.store import store


STRATEGY_ID = "top5_whale_trend_v1"
ASSETS = ("BTC", "ETH", "SOL")
INITIAL_CASH = 1_000.0
DISCLOSURE = (
    "실제 자금이 아닌 $1,000 가상 포트폴리오의 Forward Test입니다. "
    "표시된 성과는 수수료·슬리피지·funding 가정에 따라 달라질 수 있으며 "
    "미래 수익을 보장하지 않습니다."
)
CONFIG = {
    "assets": list(ASSETS),
    "evaluation_interval_sec": 3600,
    "roster_size": 5,
    "roster_freeze": "00:00 UTC",
    "position_min_wallets": 3,
    "position_consensus_pct": 65.0,
    "wallet_weight_cap_pct": 30.0,
    "flow_window_sec": 3600,
    "flow_size": 5,
    "flow_min_wallets": 3,
    "flow_consensus_pct": 60.0,
    "trend_1h_threshold_pct": 0.15,
    "trend_4h_threshold_pct": 0.0,
    "strong_weight": 0.40,
    "base_weight": 0.20,
    "max_asset_weight": 0.40,
    "max_gross_weight": 1.0,
    "confirmations": 2,
    "taker_fee_rate": 0.00045,
    "slippage_bps": 2.0,
    "extreme_funding_rate": 0.0002,
    "liq_spike_usd_1h": 10_000_000.0,
    "max_market_staleness_sec": 600,
    "leverage": 1.0,
}
CONFIG_JSON = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
CONFIG_HASH = hashlib.sha256(CONFIG_JSON.encode()).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hour_bucket(at: datetime) -> str:
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def _signed_position(position: WhalePosition) -> float:
    sign = 1.0 if position.side.value == "long" else -1.0
    return sign * float(position.size_usd)


def record_whale_flows(
    previous: list[WhalePosition],
    current: list[WhalePosition],
    *,
    observed_addresses: set[str] | None = None,
    at: datetime | None = None,
) -> int:
    """Persist signed exposure deltas without extra Hyperliquid requests.

    An empty previous snapshot is a baseline, not a set of new trades. Addresses
    whose collector request failed are excluded so a timeout cannot look like an
    exit.
    """
    if not previous:
        return 0
    at = at or _utcnow()
    observed = {a.lower() for a in observed_addresses} if observed_addresses else None
    before = {
        (p.trader_address.lower(), p.asset.upper()): _signed_position(p)
        for p in previous
        if observed is None or p.trader_address.lower() in observed
    }
    after = {
        (p.trader_address.lower(), p.asset.upper()): _signed_position(p)
        for p in current
        if observed is None or p.trader_address.lower() in observed
    }
    rows: list[WhaleFlowRow] = []
    for address, asset in sorted(set(before) | set(after)):
        old = float(before.get((address, asset), 0.0))
        new = float(after.get((address, asset), 0.0))
        delta = new - old
        if abs(delta) < 1.0:
            continue
        rows.append(
            WhaleFlowRow(
                id=f"wf_{uuid.uuid4().hex}",
                trader_address=address,
                asset=asset,
                delta_usd=delta,
                previous_usd=old,
                current_usd=new,
                created_at=at,
            )
        )
    if not rows:
        return 0
    db = SessionLocal()
    try:
        db.add_all(rows)
        db.query(WhaleFlowRow).filter(
            WhaleFlowRow.created_at < at - timedelta(hours=48)
        ).delete(synchronize_session=False)
        db.commit()
        return len(rows)
    finally:
        db.close()


def _ensure_strategy(db: Session, at: datetime) -> PaperStrategyRow:
    row = db.get(PaperStrategyRow, STRATEGY_ID)
    if row is None:
        row = PaperStrategyRow(
            id=STRATEGY_ID,
            version="1.0",
            config_json=CONFIG_JSON,
            config_hash=CONFIG_HASH,
            status="shadow",
            initial_cash=INITIAL_CASH,
            cash=INITIAL_CASH,
            peak_nav=INITIAL_CASH,
            started_at=at,
            updated_at=at,
        )
        db.add(row)
        db.flush()
    return row


def _daily_roster(db: Session, at: datetime) -> list[dict]:
    day = at.astimezone(timezone.utc).date().isoformat()
    roster_id = f"{STRATEGY_ID}:{day}"
    existing = db.get(PaperRosterRow, roster_id)
    if existing is not None:
        return list(json.loads(existing.members_json or "[]"))

    # Smart Money is the largest 15 wallets ordered by score. Freeze its first
    # five for the UTC day; do not silently replace members intraday.
    members = select_smart_money_ranks(size=15)[:5]
    payload = [
        {
            "address": item.address.lower(),
            "alias": item.alias,
            "rank": item.rank,
            "score": item.smart_money_score,
        }
        for item in members
    ]
    if len(payload) == 5:
        db.add(
            PaperRosterRow(
                id=roster_id,
                strategy_id=STRATEGY_ID,
                roster_date=day,
                members_json=json.dumps(payload),
                created_at=at,
            )
        )
        db.flush()
    return payload


def _position_consensus(asset: str, roster: list[dict]) -> tuple[str, float | None]:
    addresses = {str(item.get("address", "")).lower() for item in roster}
    positions = [
        p
        for p in store.whale_positions
        if p.asset.upper() == asset and p.trader_address.lower() in addresses
    ]
    if len(positions) < int(CONFIG["position_min_wallets"]):
        return "mixed", None
    raw_total = sum(abs(float(p.size_usd)) for p in positions)
    if raw_total <= 0:
        return "mixed", None
    cap = raw_total * float(CONFIG["wallet_weight_cap_pct"]) / 100.0
    long_usd = sum(
        min(abs(float(p.size_usd)), cap) for p in positions if p.side.value == "long"
    )
    short_usd = sum(
        min(abs(float(p.size_usd)), cap) for p in positions if p.side.value == "short"
    )
    total = long_usd + short_usd
    if total <= 0:
        return "mixed", None
    long_pct = long_usd / total * 100.0
    long_count = sum(1 for p in positions if p.side.value == "long")
    short_count = len(positions) - long_count
    threshold = float(CONFIG["position_consensus_pct"])
    minimum = int(CONFIG["position_min_wallets"])
    if long_count >= minimum and long_pct >= threshold:
        return "long", round(long_pct, 2)
    if short_count >= minimum and (100.0 - long_pct) >= threshold:
        return "short", round(long_pct, 2)
    return "mixed", round(long_pct, 2)


def _flow_consensus(db: Session, asset: str, at: datetime) -> tuple[str, float | None]:
    rows = (
        db.query(
            WhaleFlowRow.trader_address,
            func.sum(WhaleFlowRow.delta_usd).label("net_flow"),
        )
        .filter(
            WhaleFlowRow.asset == asset,
            WhaleFlowRow.created_at > at - timedelta(seconds=int(CONFIG["flow_window_sec"])),
            WhaleFlowRow.created_at <= at,
        )
        .group_by(WhaleFlowRow.trader_address)
        .all()
    )
    ranked = sorted(
        [(str(address), float(net or 0.0)) for address, net in rows if abs(float(net or 0.0)) >= 1.0],
        key=lambda item: abs(item[1]),
        reverse=True,
    )[: int(CONFIG["flow_size"])]
    if len(ranked) < int(CONFIG["flow_min_wallets"]):
        return "unavailable", None
    positive = sum(value for _, value in ranked if value > 0)
    negative = sum(abs(value) for _, value in ranked if value < 0)
    total = positive + negative
    if total <= 0:
        return "mixed", None
    long_pct = positive / total * 100.0
    threshold = float(CONFIG["flow_consensus_pct"])
    if long_pct >= threshold:
        return "long", round(long_pct, 2)
    if 100.0 - long_pct >= threshold:
        return "short", round(long_pct, 2)
    return "mixed", round(long_pct, 2)


def _snapshot_at_or_before(db: Session, asset: str, at: datetime) -> MarketSnapshotRow | None:
    return (
        db.query(MarketSnapshotRow)
        .filter(MarketSnapshotRow.asset == asset, MarketSnapshotRow.timestamp <= at)
        .order_by(MarketSnapshotRow.timestamp.desc())
        .first()
    )


def _market_trend(
    db: Session, asset: str, at: datetime
) -> tuple[str, float | None, float | None, MarketSnapshotRow | None]:
    latest = _snapshot_at_or_before(db, asset, at)
    one = _snapshot_at_or_before(db, asset, at - timedelta(hours=1))
    four = _snapshot_at_or_before(db, asset, at - timedelta(hours=4))
    if latest is None or one is None or four is None:
        return "mixed", None, None, latest
    latest_ts = latest.timestamp
    if latest_ts.tzinfo is None:
        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
    if (at - latest_ts).total_seconds() > int(CONFIG["max_market_staleness_sec"]):
        return "mixed", None, None, latest
    if one.mark_price <= 0 or four.mark_price <= 0:
        return "mixed", None, None, latest
    r1 = (latest.mark_price / one.mark_price - 1.0) * 100.0
    r4 = (latest.mark_price / four.mark_price - 1.0) * 100.0
    if r1 > float(CONFIG["trend_1h_threshold_pct"]) and r4 > float(CONFIG["trend_4h_threshold_pct"]):
        trend = "up"
    elif r1 < -float(CONFIG["trend_1h_threshold_pct"]) and r4 < -float(CONFIG["trend_4h_threshold_pct"]):
        trend = "down"
    else:
        trend = "mixed"
    return trend, round(r1, 4), round(r4, 4), latest


def _raw_decision(position: str, flow: str, trend: str) -> tuple[str, float, str]:
    if position in {"long", "short"} and flow in {"long", "short"} and position != flow:
        return "wait", 0.0, "Top 5 positions and recent flow conflict"
    if position == "long" and flow == "long" and trend == "up":
        return "long", float(CONFIG["strong_weight"]), "Top 5 positions, flow, and trend agree"
    if position == "short" and flow == "short" and trend == "down":
        return "short", float(CONFIG["strong_weight"]), "Top 5 positions, flow, and trend agree"
    if position == "long" and flow in {"mixed", "unavailable"} and trend == "up":
        return "long", float(CONFIG["base_weight"]), "Top 5 positions confirmed by trend"
    if position == "short" and flow in {"mixed", "unavailable"} and trend == "down":
        return "short", float(CONFIG["base_weight"]), "Top 5 positions confirmed by trend"
    if position == "mixed" and flow == "long" and trend == "up":
        return "long", float(CONFIG["base_weight"]), "Recent Top 5 flow confirmed by trend"
    if position == "mixed" and flow == "short" and trend == "down":
        return "short", float(CONFIG["base_weight"]), "Recent Top 5 flow confirmed by trend"
    return "wait", 0.0, "Whale direction lacks market-trend confirmation"


def _apply_risk_filters(
    db: Session,
    *,
    asset: str,
    action: str,
    weight: float,
    latest: MarketSnapshotRow | None,
    at: datetime,
) -> tuple[float, dict]:
    if action == "wait" or weight <= 0:
        return 0.0, {"funding_reduced": False, "liquidation_reduced": False}
    funding = float(latest.funding_rate) if latest is not None else 0.0
    threshold = float(CONFIG["extreme_funding_rate"])
    funding_reduced = (action == "long" and funding > threshold) or (
        action == "short" and funding < -threshold
    )
    liq_total = float(
        db.query(func.coalesce(func.sum(LiquidationRow.size_usd), 0.0))
        .filter(
            LiquidationRow.asset == asset,
            LiquidationRow.timestamp > at - timedelta(hours=1),
            LiquidationRow.timestamp <= at,
        )
        .scalar()
        or 0.0
    )
    liquidation_reduced = liq_total >= float(CONFIG["liq_spike_usd_1h"])
    if funding_reduced and liquidation_reduced:
        adjusted = 0.0
    elif funding_reduced or liquidation_reduced:
        adjusted = weight / 2.0
    else:
        adjusted = weight
    return adjusted, {
        "funding_rate": funding,
        "funding_reduced": funding_reduced,
        "liq_1h_usd": round(liq_total, 2),
        "liquidation_reduced": liquidation_reduced,
        "before_weight": weight,
        "after_weight": adjusted,
    }


def _marks(db: Session, at: datetime) -> dict[str, float]:
    result: dict[str, float] = {}
    for asset in ASSETS:
        row = _snapshot_at_or_before(db, asset, at)
        if row is not None and row.mark_price > 0:
            result[asset] = float(row.mark_price)
    return result


def _latest_marks(db: Session) -> dict[str, float]:
    result: dict[str, float] = {}
    for asset in ASSETS:
        row = (
            db.query(MarketSnapshotRow)
            .filter(MarketSnapshotRow.asset == asset)
            .order_by(MarketSnapshotRow.timestamp.desc())
            .first()
        )
        if row is not None and row.mark_price > 0:
            result[asset] = float(row.mark_price)
    return result


def _unrealized(position: PaperPositionRow, mark: float) -> float:
    sign = 1.0 if position.direction == "long" else -1.0
    return float(position.quantity) * (mark - float(position.average_entry)) * sign


def _portfolio_values(
    db: Session, strategy: PaperStrategyRow, marks: dict[str, float]
) -> tuple[float, float, float]:
    gross = 0.0
    unrealized = 0.0
    for position in db.query(PaperPositionRow).filter(PaperPositionRow.strategy_id == strategy.id).all():
        mark = marks.get(position.asset)
        if mark is None:
            continue
        gross += abs(float(position.quantity) * mark)
        unrealized += _unrealized(position, mark)
    nav = float(strategy.cash) + unrealized
    return nav, gross, unrealized


def _accrue_funding(db: Session, strategy: PaperStrategyRow, marks: dict[str, float]) -> None:
    payment_total = 0.0
    for position in db.query(PaperPositionRow).filter(PaperPositionRow.strategy_id == strategy.id).all():
        mark = marks.get(position.asset)
        tick = (store.market_ticks or {}).get(position.asset) or {}
        if mark is None:
            continue
        try:
            rate = float(tick.get("funding_rate") or 0.0)
        except (TypeError, ValueError):
            rate = 0.0
        sign = 1.0 if position.direction == "long" else -1.0
        payment_total += -sign * abs(float(position.quantity) * mark) * rate
    strategy.cash += payment_total
    strategy.cumulative_funding += payment_total


def _add_trade(
    db: Session,
    strategy: PaperStrategyRow,
    decision: PaperDecisionRow,
    *,
    side: str,
    action: str,
    quantity: float,
    mark: float,
    realized: float = 0.0,
) -> tuple[float, float, float]:
    slip_rate = float(CONFIG["slippage_bps"]) / 10_000.0
    fill = mark * (1.0 + slip_rate if side == "buy" else 1.0 - slip_rate)
    notional = abs(quantity * fill)
    fee = notional * float(CONFIG["taker_fee_rate"])
    slippage = abs(fill - mark) * abs(quantity)
    db.add(
        PaperTradeRow(
            id=f"pt_{uuid.uuid4().hex}",
            strategy_id=strategy.id,
            decision_id=decision.id,
            asset=decision.asset,
            side=side,
            action=action,
            quantity=abs(quantity),
            mark_price=mark,
            fill_price=fill,
            notional_usd=notional,
            fee_usd=fee,
            slippage_usd=slippage,
            realized_pnl_usd=realized,
            created_at=decision.created_at,
        )
    )
    strategy.cash += realized - fee
    strategy.realized_pnl += realized
    strategy.cumulative_fees += fee
    strategy.cumulative_slippage += slippage
    return fill, fee, slippage


def _rebalance_position(
    db: Session,
    strategy: PaperStrategyRow,
    decision: PaperDecisionRow,
    target_notional: float,
) -> None:
    mark = float(decision.mark_price or 0.0)
    if mark <= 0:
        return
    position_id = f"{strategy.id}:{decision.asset}"
    position = db.get(PaperPositionRow, position_id)
    desired_sign = 1.0 if decision.action == "long" else -1.0 if decision.action == "short" else 0.0
    desired_qty = desired_sign * max(0.0, target_notional) / mark
    current_qty = 0.0
    if position is not None:
        current_qty = float(position.quantity) * (1.0 if position.direction == "long" else -1.0)
    if abs(desired_qty - current_qty) * mark < 0.01:
        return

    now = decision.created_at
    # Close first when reducing through zero or reversing.
    if position is not None and current_qty != 0 and (desired_qty == 0 or current_qty * desired_qty < 0):
        side = "sell" if current_qty > 0 else "buy"
        slip = float(CONFIG["slippage_bps"]) / 10_000.0
        close_fill = mark * (1.0 + slip if side == "buy" else 1.0 - slip)
        sign = 1.0 if current_qty > 0 else -1.0
        realized = abs(current_qty) * (close_fill - float(position.average_entry)) * sign
        _add_trade(
            db,
            strategy,
            decision,
            side=side,
            action="close",
            quantity=abs(current_qty),
            mark=mark,
            realized=realized,
        )
        db.delete(position)
        db.flush()
        position = None
        current_qty = 0.0

    if desired_qty == 0:
        return

    if position is None:
        side = "buy" if desired_qty > 0 else "sell"
        fill, _, _ = _add_trade(
            db,
            strategy,
            decision,
            side=side,
            action="open",
            quantity=abs(desired_qty),
            mark=mark,
        )
        db.add(
            PaperPositionRow(
                id=position_id,
                strategy_id=strategy.id,
                asset=decision.asset,
                direction="long" if desired_qty > 0 else "short",
                quantity=abs(desired_qty),
                average_entry=fill,
                opened_at=now,
                updated_at=now,
            )
        )
        return

    current_abs = abs(current_qty)
    desired_abs = abs(desired_qty)
    if desired_abs > current_abs:
        add_qty = desired_abs - current_abs
        side = "buy" if current_qty > 0 else "sell"
        fill, _, _ = _add_trade(
            db,
            strategy,
            decision,
            side=side,
            action="increase",
            quantity=add_qty,
            mark=mark,
        )
        position.average_entry = (
            float(position.average_entry) * current_abs + fill * add_qty
        ) / desired_abs
        position.quantity = desired_abs
        position.updated_at = now
    elif desired_abs < current_abs:
        reduce_qty = current_abs - desired_abs
        side = "sell" if current_qty > 0 else "buy"
        slip = float(CONFIG["slippage_bps"]) / 10_000.0
        fill = mark * (1.0 + slip if side == "buy" else 1.0 - slip)
        sign = 1.0 if current_qty > 0 else -1.0
        realized = reduce_qty * (fill - float(position.average_entry)) * sign
        _add_trade(
            db,
            strategy,
            decision,
            side=side,
            action="reduce",
            quantity=reduce_qty,
            mark=mark,
            realized=realized,
        )
        position.quantity = desired_abs
        position.updated_at = now


def run_paper_portfolio(at: datetime | None = None) -> bool:
    """Evaluate one idempotent hourly strategy bucket.

    Returns True when a new bucket was recorded, False when already processed.
    """
    # Preserve the forward-test ledger during incomplete source cycles. In
    # particular, missing liquidation evidence must not mean zero liq risk.
    if any(state.status != "ok" for state in store.collectors.values()):
        return False
    at = (at or _utcnow()).astimezone(timezone.utc)
    bucket = _hour_bucket(at)
    db = SessionLocal()
    try:
        strategy = _ensure_strategy(db, at)
        existing = (
            db.query(PaperDecisionRow)
            .filter(PaperDecisionRow.strategy_id == strategy.id, PaperDecisionRow.bucket == bucket)
            .first()
        )
        if existing is not None:
            db.rollback()
            return False

        roster = _daily_roster(db, at)
        marks = _marks(db, at)
        _accrue_funding(db, strategy, marks)
        nav_before, _, _ = _portfolio_values(db, strategy, marks)
        if strategy.benchmark_start_price is None and marks.get("BTC"):
            strategy.benchmark_start_price = marks["BTC"]

        decisions: list[PaperDecisionRow] = []
        for asset in ASSETS:
            position_signal, position_long_pct = _position_consensus(asset, roster)
            flow_signal, flow_long_pct = _flow_consensus(db, asset, at)
            trend, r1, r4, latest = _market_trend(db, asset, at)
            raw_action, weight, reason = _raw_decision(position_signal, flow_signal, trend)
            weight, risk = _apply_risk_filters(
                db,
                asset=asset,
                action=raw_action,
                weight=weight,
                latest=latest,
                at=at,
            )
            if weight <= 0:
                raw_action = "wait"

            previous = (
                db.query(PaperDecisionRow)
                .filter(
                    PaperDecisionRow.strategy_id == strategy.id,
                    PaperDecisionRow.asset == asset,
                )
                .order_by(PaperDecisionRow.created_at.desc())
                .first()
            )
            confirmed = previous is not None and previous.raw_action == raw_action
            current = db.get(PaperPositionRow, f"{strategy.id}:{asset}")
            if confirmed:
                action = raw_action
                target_weight = weight
            elif current is not None and marks.get(asset) and nav_before > 0:
                action = current.direction
                target_weight = min(
                    float(CONFIG["max_asset_weight"]),
                    abs(float(current.quantity) * marks[asset]) / nav_before,
                )
                reason += "; awaiting second confirmation, holding current position"
            else:
                action = "wait"
                target_weight = 0.0
                reason += "; awaiting second confirmation"

            decision = PaperDecisionRow(
                id=f"{strategy.id}:{bucket}:{asset}",
                strategy_id=strategy.id,
                bucket=bucket,
                asset=asset,
                roster_json=json.dumps(roster),
                position_signal=position_signal,
                position_long_pct=position_long_pct,
                flow_signal=flow_signal,
                flow_long_pct=flow_long_pct,
                trend=trend,
                return_1h_pct=r1,
                return_4h_pct=r4,
                raw_action=raw_action,
                action=action,
                target_weight=target_weight,
                risk_json=json.dumps(risk),
                reason=reason,
                mark_price=marks.get(asset),
                created_at=at,
            )
            db.add(decision)
            decisions.append(decision)
        db.flush()

        total_weight = sum(max(0.0, d.target_weight) for d in decisions)
        scale = min(1.0, float(CONFIG["max_gross_weight"]) / total_weight) if total_weight > 0 else 1.0
        for decision in decisions:
            decision.target_weight = min(
                float(CONFIG["max_asset_weight"]), decision.target_weight * scale
            )
            _rebalance_position(
                db,
                strategy,
                decision,
                max(0.0, nav_before) * decision.target_weight,
            )

        nav, gross, unrealized = _portfolio_values(db, strategy, marks)
        strategy.peak_nav = max(float(strategy.peak_nav), nav)
        strategy.updated_at = at
        drawdown = (nav / strategy.peak_nav - 1.0) * 100.0 if strategy.peak_nav > 0 else 0.0
        benchmark = None
        if strategy.benchmark_start_price and marks.get("BTC"):
            benchmark = strategy.initial_cash * marks["BTC"] / strategy.benchmark_start_price
        db.add(
            PaperEquityRow(
                id=f"{strategy.id}:{bucket}",
                strategy_id=strategy.id,
                bucket=bucket,
                cash=strategy.cash,
                gross_exposure_usd=gross,
                unrealized_pnl_usd=unrealized,
                realized_pnl_usd=strategy.realized_pnl,
                nav=nav,
                return_pct=(nav / strategy.initial_cash - 1.0) * 100.0,
                benchmark_nav=benchmark,
                drawdown_pct=drawdown,
                cumulative_fees=strategy.cumulative_fees,
                cumulative_slippage=strategy.cumulative_slippage,
                cumulative_funding=strategy.cumulative_funding,
                created_at=at,
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _position_models(
    db: Session, strategy: PaperStrategyRow, marks: dict[str, float], nav: float
) -> list[PaperPortfolioPosition]:
    items: list[PaperPortfolioPosition] = []
    for row in db.query(PaperPositionRow).filter(PaperPositionRow.strategy_id == strategy.id).all():
        mark = marks.get(row.asset)
        notional = abs(float(row.quantity) * mark) if mark is not None else 0.0
        unrealized = _unrealized(row, mark) if mark is not None else 0.0
        items.append(
            PaperPortfolioPosition(
                asset=row.asset,
                direction=row.direction,
                quantity=row.quantity,
                average_entry=row.average_entry,
                mark_price=mark,
                notional_usd=round(notional, 2),
                unrealized_pnl_usd=round(unrealized, 2),
                weight_pct=round(notional / nav * 100.0, 2) if nav > 0 else 0.0,
                updated_at=row.updated_at,
            )
        )
    return sorted(items, key=lambda item: item.notional_usd, reverse=True)


def get_paper_summary() -> PaperPortfolioSummary:
    db = SessionLocal()
    try:
        now = _utcnow()
        strategy = _ensure_strategy(db, now)
        db.commit()
        marks = _latest_marks(db)
        latest = (
            db.query(PaperEquityRow)
            .filter(PaperEquityRow.strategy_id == strategy.id)
            .order_by(PaperEquityRow.created_at.desc())
            .first()
        )
        if latest is not None:
            nav = float(latest.nav)
            gross = float(latest.gross_exposure_usd)
            unrealized = float(latest.unrealized_pnl_usd)
            benchmark = latest.benchmark_nav
            updated_at = latest.created_at
        else:
            nav, gross, unrealized = _portfolio_values(db, strategy, marks)
            benchmark = strategy.initial_cash
            updated_at = strategy.updated_at
        trade_count = db.query(PaperTradeRow).filter(PaperTradeRow.strategy_id == strategy.id).count()
        closed = (
            db.query(PaperTradeRow)
            .filter(
                PaperTradeRow.strategy_id == strategy.id,
                PaperTradeRow.action.in_(["reduce", "close"]),
            )
            .all()
        )
        wins = sum(1 for row in closed if row.realized_pnl_usd > 0)
        max_dd = float(
            db.query(func.coalesce(func.min(PaperEquityRow.drawdown_pct), 0.0))
            .filter(PaperEquityRow.strategy_id == strategy.id)
            .scalar()
            or 0.0
        )
        decisions = (
            db.query(PaperDecisionRow)
            .filter(PaperDecisionRow.strategy_id == strategy.id)
            .order_by(PaperDecisionRow.created_at.desc(), PaperDecisionRow.asset.asc())
            .limit(3)
            .all()
        )
        return PaperPortfolioSummary(
            strategy_id=strategy.id,
            version=strategy.version,
            status=strategy.status,
            initial_cash=strategy.initial_cash,
            nav=round(nav, 2),
            return_pct=round((nav / strategy.initial_cash - 1.0) * 100.0, 3),
            benchmark_nav=round(float(benchmark), 2) if benchmark is not None else None,
            benchmark_return_pct=(
                round((float(benchmark) / strategy.initial_cash - 1.0) * 100.0, 3)
                if benchmark is not None
                else None
            ),
            max_drawdown_pct=round(max_dd, 3),
            cash=round(float(strategy.cash), 2),
            gross_exposure_usd=round(gross, 2),
            realized_pnl_usd=round(float(strategy.realized_pnl), 2),
            unrealized_pnl_usd=round(unrealized, 2),
            cumulative_fees=round(float(strategy.cumulative_fees), 4),
            cumulative_slippage=round(float(strategy.cumulative_slippage), 4),
            cumulative_funding=round(float(strategy.cumulative_funding), 4),
            trades_count=trade_count,
            closed_trades_count=len(closed),
            win_rate=round(wins / len(closed) * 100.0, 1) if closed else None,
            current_positions=_position_models(db, strategy, marks, nav),
            last_decisions=[
                {
                    "asset": row.asset,
                    "position_signal": row.position_signal,
                    "flow_signal": row.flow_signal,
                    "trend": row.trend,
                    "action": row.action,
                    "target_weight_pct": round(row.target_weight * 100.0, 1),
                    "reason": row.reason,
                    "as_of": row.created_at.isoformat(),
                }
                for row in decisions
            ],
            started_at=strategy.started_at,
            updated_at=updated_at,
            warming_up=len(decisions) < 3 or trade_count == 0,
            disclosure=DISCLOSURE,
        )
    finally:
        db.close()


def get_equity_curve(limit: int = 1000) -> list[PaperEquityPoint]:
    db = SessionLocal()
    try:
        rows = (
            db.query(PaperEquityRow)
            .filter(PaperEquityRow.strategy_id == STRATEGY_ID)
            .order_by(PaperEquityRow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            PaperEquityPoint(
                nav=row.nav,
                benchmark_nav=row.benchmark_nav,
                drawdown_pct=row.drawdown_pct,
                created_at=row.created_at,
            )
            for row in reversed(rows)
        ]
    finally:
        db.close()


def get_trades(limit: int = 100) -> list[PaperPortfolioTrade]:
    db = SessionLocal()
    try:
        rows = (
            db.query(PaperTradeRow)
            .filter(PaperTradeRow.strategy_id == STRATEGY_ID)
            .order_by(PaperTradeRow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            PaperPortfolioTrade(
                id=row.id,
                asset=row.asset,
                side=row.side,
                action=row.action,
                quantity=row.quantity,
                mark_price=row.mark_price,
                fill_price=row.fill_price,
                notional_usd=row.notional_usd,
                fee_usd=row.fee_usd,
                slippage_usd=row.slippage_usd,
                realized_pnl_usd=row.realized_pnl_usd,
                created_at=row.created_at,
            )
            for row in rows
        ]
    finally:
        db.close()


def get_strategy_detail() -> PaperStrategyDetail:
    db = SessionLocal()
    try:
        row = _ensure_strategy(db, _utcnow())
        db.commit()
        return PaperStrategyDetail(
            strategy_id=row.id,
            version=row.version,
            status=row.status,
            config_hash=row.config_hash,
            config=json.loads(row.config_json),
            started_at=row.started_at,
        )
    finally:
        db.close()
