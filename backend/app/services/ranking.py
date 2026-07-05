from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import SmartMoneyRank, TraderProfile
from app.services.store import store


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _momentum_score(trader: TraderProfile) -> float:
    spark = trader.sparkline or [0]
    if len(spark) < 2:
        return max(0.0, trader.pnl_change_pct)
    delta = spark[-1] - spark[0]
    return max(0.0, min(100.0, 50 + delta + trader.pnl_change_pct * 2))


def _consistency_score(trader: TraderProfile) -> float:
    trade_factor = min(trader.total_trades, 500) / 500 * 40
    win_factor = trader.win_rate * 0.5
    hold_penalty = 0 if trader.avg_hold_hours >= 1 else 10
    return max(0.0, min(100.0, trade_factor + win_factor - hold_penalty))


def compute_smart_money_score(trader: TraderProfile) -> tuple[float, float, float]:
    momentum = _momentum_score(trader)
    consistency = _consistency_score(trader)
    risk_adj = max(0.0, 100 - abs(trader.risk_score - 55) * 0.8)
    score = (
        trader.win_rate * 0.35
        + momentum * 0.25
        + consistency * 0.25
        + risk_adj * 0.15
    )
    return round(score, 1), round(momentum, 1), round(consistency, 1)


def run_ranking_pipeline() -> list[SmartMoneyRank]:
    scored: list[SmartMoneyRank] = []
    score_map: dict[str, float] = {}

    for trader in store.traders:
        score, momentum, consistency = compute_smart_money_score(trader)
        score_map[trader.address] = score
        scored.append(
            SmartMoneyRank(
                address=trader.address,
                alias=trader.alias,
                rank=0,
                smart_money_score=score,
                pnl_usd=trader.pnl_usd,
                win_rate=trader.win_rate,
                pnl_change_pct=trader.pnl_change_pct,
                strategy_tags=trader.strategy_tags,
                risk_score=trader.risk_score,
                momentum_score=momentum,
                consistency_score=consistency,
                sparkline=trader.sparkline,
            )
        )

    scored.sort(key=lambda r: r.smart_money_score, reverse=True)
    for idx, item in enumerate(scored, start=1):
        item.rank = idx

    # Keep trader list ranks aligned with smart money ranking
    rank_map = {item.address: item.rank for item in scored}
    updated_traders = []
    for trader in store.traders:
        updated_traders.append(trader.model_copy(update={"rank": rank_map.get(trader.address, trader.rank)}))
    updated_traders.sort(key=lambda t: t.rank)

    with store._lock:
        store.rankings = scored
        store.traders = updated_traders
        store.last_ranking_at = _utcnow()

    store.persist_traders(updated_traders, score_map)
    store.refresh_dashboard()
    return scored
