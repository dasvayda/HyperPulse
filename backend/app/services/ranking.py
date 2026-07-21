from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone

from app.models.schemas import SmartMoneyRank, TraderProfile
from app.services.store import store


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100.0))


def _pnl_score(trader: TraderProfile, low: float, high: float) -> float:
    return _normalize(math.log1p(max(0.0, trader.pnl_usd)), low, high)


def _momentum_score(trader: TraderProfile, low: float, high: float) -> float:
    return _normalize(trader.pnl_change_pct, low, high)


def _consistency_score(trader: TraderProfile) -> float:
    spark = [v for v in (trader.sparkline or []) if v != 0]
    if len(spark) < 2:
        return 0.0

    positive_steps = sum(1 for i in range(1, len(spark)) if spark[i] >= spark[i - 1])
    trend = positive_steps / (len(spark) - 1) * 60.0

    mean = statistics.fmean(spark)
    if mean == 0:
        stability = 20.0
    else:
        vol = statistics.pstdev(spark) / abs(mean)
        stability = max(0.0, 40.0 - vol * 100.0)

    return round(max(0.0, min(100.0, trend + stability)), 1)


def compute_smart_money_score(
    trader: TraderProfile,
    *,
    pnl_low: float,
    pnl_high: float,
    roi_low: float,
    roi_high: float,
) -> tuple[float, float, float]:
    pnl_component = _pnl_score(trader, pnl_low, pnl_high)
    momentum = _momentum_score(trader, roi_low, roi_high)
    consistency = _consistency_score(trader)
    risk_adj = max(0.0, 100.0 - trader.risk_score)

    if trader.win_rate > 0 or trader.total_trades > 0:
        score = (
            trader.win_rate * 0.20
            + pnl_component * 0.25
            + momentum * 0.25
            + consistency * 0.20
            + risk_adj * 0.10
        )
    else:
        # Live leaderboard mode: rank on PnL, ROI, curve stability, and risk.
        score = (
            pnl_component * 0.35
            + momentum * 0.30
            + consistency * 0.20
            + risk_adj * 0.15
        )

    return round(score, 1), round(momentum, 1), round(consistency, 1)


def run_ranking_pipeline() -> list[SmartMoneyRank]:
    traders = store.traders
    if not traders:
        with store._lock:
            store.rankings = []
            store.last_ranking_at = _utcnow()
        return []

    pnl_logs = [math.log1p(max(0.0, t.pnl_usd)) for t in traders]
    rois = [t.pnl_change_pct for t in traders]
    pnl_low, pnl_high = min(pnl_logs), max(pnl_logs)
    roi_low, roi_high = min(rois), max(rois)

    scored: list[SmartMoneyRank] = []
    score_map: dict[str, float] = {}
    inference_map = {
        item.trader_address.lower(): item.strategy for item in store.inferences
    }

    for trader in traders:
        score, momentum, consistency = compute_smart_money_score(
            trader,
            pnl_low=pnl_low,
            pnl_high=pnl_high,
            roi_low=roi_low,
            roi_high=roi_high,
        )
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
                inferred_strategy=inference_map.get(trader.address.lower()),
                risk_score=trader.risk_score,
                momentum_score=momentum,
                consistency_score=consistency,
                sparkline=trader.sparkline,
            )
        )

    scored.sort(key=lambda r: (r.smart_money_score, r.pnl_usd), reverse=True)
    for idx, item in enumerate(scored, start=1):
        item.rank = idx

    rank_map = {item.address: item.rank for item in scored}
    updated_traders = []
    for trader in traders:
        updated_traders.append(trader.model_copy(update={"rank": rank_map.get(trader.address, trader.rank)}))
    updated_traders.sort(key=lambda t: t.rank)

    with store._lock:
        store.rankings = scored
        store.traders = updated_traders
        store.last_ranking_at = _utcnow()

    store.persist_traders(updated_traders, score_map)
    store.refresh_dashboard()
    return scored
