from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone

from app.models.schemas import SmartMoneyRank, TraderProfile
from app.services.store import store

# Smart Money: largest accounts by account value, then score-sorted.
SMART_MONEY_SIZE = 15
# Performance Ranking: aim for ~N names via |PnL| or |uPnL| threshold.
PERFORMANCE_TARGET = 30
PERFORMANCE_BASE_THRESHOLD_USD = 1_000_000.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 50.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100.0))


def _robust_bounds(
    values: list[float],
    *,
    lo_pct: float = 10.0,
    hi_pct: float = 90.0,
) -> tuple[float, float]:
    """Spread for 0–100 normalize that ignores extreme ROI/PnL outliers.

    Prefer Tukey inliers (Q1/Q3 ± 1.5·IQR). Fall back to nearest-rank
    percentiles, then trim min/max once if the window still collapses.
    """
    if not values:
        return 0.0, 1.0
    ordered = sorted(values)
    n = len(ordered)
    if n == 1:
        v = ordered[0]
        return v, v

    def _at(pct: float) -> float:
        idx = int(round((n - 1) * (pct / 100.0)))
        idx = max(0, min(n - 1, idx))
        return ordered[idx]

    if n >= 4:
        q1 = _at(25.0)
        q3 = _at(75.0)
        iqr = q3 - q1
        if iqr > 0:
            fence_lo = q1 - 1.5 * iqr
            fence_hi = q3 + 1.5 * iqr
            inliers = [v for v in ordered if fence_lo <= v <= fence_hi]
            if len(inliers) >= 2 and inliers[-1] > inliers[0]:
                return inliers[0], inliers[-1]

    low = _at(lo_pct)
    high = _at(hi_pct)
    if high > low:
        return low, high

    # Many ties or tiny sample — drop one extreme on each side when possible.
    if n >= 3:
        return ordered[1], ordered[-2]
    return ordered[0], ordered[-1]


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
    pnl_low, pnl_high = _robust_bounds(pnl_logs)
    roi_low, roi_high = _robust_bounds(rois)

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
        open_roi_pct, open_unrealized_pnl_usd = store.summarize_open_pnl(trader.address)
        scored.append(
            SmartMoneyRank(
                address=trader.address,
                alias=trader.alias,
                rank=0,
                smart_money_score=score,
                pnl_usd=trader.pnl_usd,
                account_value_usd=trader.account_value_usd,
                win_rate=trader.win_rate,
                pnl_change_pct=trader.pnl_change_pct,
                strategy_tags=trader.strategy_tags,
                inferred_strategy=inference_map.get(trader.address.lower()),
                open_roi_pct=open_roi_pct,
                open_unrealized_pnl_usd=open_unrealized_pnl_usd,
                risk_score=trader.risk_score,
                momentum_score=momentum,
                consistency_score=consistency,
                sparkline=trader.sparkline,
            )
        )

    scored.sort(key=lambda r: (r.smart_money_score, r.pnl_usd), reverse=True)
    for idx, item in enumerate(scored, start=1):
        item.rank = idx

    # Keep trader.rank aligned with full score order (internal / detail links).
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


def _eligibility_usd(rank: SmartMoneyRank) -> float:
    """Max of |all-time PnL| and |open uPnL| — used as Ranking inclusion metric."""
    return max(abs(rank.pnl_usd), abs(rank.open_unrealized_pnl_usd or 0.0))


def select_smart_money_ranks(
    ranks: list[SmartMoneyRank] | None = None,
    *,
    size: int = SMART_MONEY_SIZE,
) -> list[SmartMoneyRank]:
    """Largest accounts by account value, then sorted by smart money score."""
    source = ranks if ranks is not None else store.rankings
    if not source:
        return []
    by_size = sorted(source, key=lambda r: r.account_value_usd, reverse=True)[:size]
    ordered = sorted(
        by_size,
        key=lambda r: (r.smart_money_score, r.pnl_usd, r.account_value_usd),
        reverse=True,
    )
    return [
        item.model_copy(update={"rank": idx})
        for idx, item in enumerate(ordered, start=1)
    ]


def resolve_performance_threshold(
    ranks: list[SmartMoneyRank],
    *,
    target: int = PERFORMANCE_TARGET,
    base_threshold: float = PERFORMANCE_BASE_THRESHOLD_USD,
) -> float:
    """Pick |PnL| or |uPnL| floor so ~`target` names qualify.

    Starts from `base_threshold` ($1M). If too many qualify, raise to the
    target-th metric; if too few, lower to the target-th metric (or 0).
    """
    if not ranks:
        return base_threshold
    metrics = sorted((_eligibility_usd(r) for r in ranks), reverse=True)
    if len(metrics) >= target:
        target_cut = metrics[target - 1]
    else:
        target_cut = 0.0
    qualified_at_base = sum(1 for m in metrics if m >= base_threshold)
    if qualified_at_base >= target:
        return max(base_threshold, target_cut)
    return target_cut


def select_performance_ranks(
    ranks: list[SmartMoneyRank] | None = None,
    *,
    target: int = PERFORMANCE_TARGET,
    base_threshold: float = PERFORMANCE_BASE_THRESHOLD_USD,
) -> tuple[list[SmartMoneyRank], float]:
    """Performance Ranking: filter by size threshold, sort Open ROI then PnL."""
    source = ranks if ranks is not None else store.rankings
    if not source:
        return [], base_threshold
    threshold = resolve_performance_threshold(
        source, target=target, base_threshold=base_threshold
    )
    eligible = [r for r in source if _eligibility_usd(r) >= threshold]
    eligible.sort(
        key=lambda r: (
            r.open_roi_pct is not None,
            r.open_roi_pct if r.open_roi_pct is not None else float("-inf"),
            r.pnl_usd,
            abs(r.open_unrealized_pnl_usd or 0.0),
        ),
        reverse=True,
    )
    trimmed = eligible[:target]
    items = [
        item.model_copy(update={"rank": idx})
        for idx, item in enumerate(trimmed, start=1)
    ]
    return items, threshold
