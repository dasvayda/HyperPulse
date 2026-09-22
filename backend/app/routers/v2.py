from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.orm import LiquidationRow, MarketSnapshotRow
from app.models.schemas import (
    AlertHistoryItem,
    BiggestPosition,
    CohortBiasResponse,
    CoinPulse,
    FearGreedIndex,
    LiqProximityRow,
    MarketBrief,
    MarketInsight,
    MarketPulse,
    MarketStatus,
    PerformanceRankingResponse,
    PipelineStatus,
    SmartMoneyRank,
    StrategyInference,
    TraderFillsSummary,
    WhaleBookSummary,
)
from app.collectors.fills import fetch_recent_fills
from app.services.alerts import process_alert_triggers
from app.services.cohort_bias import compute_cohort_bias
from app.services.inference import run_inference_pipeline
from app.services.liq_proximity import list_liq_proximity
from app.services.liq_windows import pressure_line, rollup_liq_windows
from app.services.market_brief import generate_market_brief
from app.services.market_pulse import compute_market_pulse
from app.services.ranking import (
    PERFORMANCE_BASE_THRESHOLD_USD,
    PERFORMANCE_TARGET,
    SMART_MONEY_SIZE,
    run_ranking_pipeline,
    select_performance_ranks,
    select_smart_money_ranks,
)
from app.services.store import store
from app.services.whale_book import (
    asset_market_tag,
    list_biggest_positions,
    summarize_whale_book,
    whale_bias_label,
)

router = APIRouter(prefix="/api/v2", tags=["v2"])


@router.get("/rankings", response_model=list[SmartMoneyRank])
def list_rankings(limit: int = Query(default=SMART_MONEY_SIZE, le=100)) -> list[SmartMoneyRank]:
    """Smart Money: top accounts by size, ordered by smart money score."""
    if not store.rankings:
        run_ranking_pipeline()
    items = select_smart_money_ranks()
    return items[:limit]


@router.get("/performance", response_model=PerformanceRankingResponse)
def list_performance_rankings(
    target: int = Query(default=PERFORMANCE_TARGET, ge=5, le=100),
) -> PerformanceRankingResponse:
    """Performance Ranking: Open ROI / PnL among names above auto-tuned |PnL| or |uPnL| floor."""
    if not store.rankings:
        run_ranking_pipeline()
    items, threshold = select_performance_ranks(target=target)
    return PerformanceRankingResponse(
        threshold_usd=threshold,
        target_count=target,
        base_threshold_usd=PERFORMANCE_BASE_THRESHOLD_USD,
        items=items,
    )


@router.get("/insights", response_model=list[MarketInsight])
def list_insights(limit: int = Query(default=20, le=50)) -> list[MarketInsight]:
    items = store.insights[:limit]
    # Re-attach latest pulse in case resolve landed after last inference.
    try:
        from app.services.pulse import attach_pulses_to_insights

        attach_pulses_to_insights(items)
    except Exception:
        pass
    return items


@router.get("/insights/brief", response_model=MarketBrief)
async def get_market_brief(
    force: bool = Query(default=False),
    asset: str | None = Query(default=None),
) -> MarketBrief:
    """Desk-style Market Brief (LLM or template fallback). Optional per-coin slice."""
    want = (asset or "").strip().upper() or None
    if want:
        brief = await generate_market_brief(force=force, asset=want)
    elif store.market_brief is not None and not force:
        brief = store.market_brief
    else:
        brief = await generate_market_brief(force=force)

    try:
        from app.services.pulse import brief_pulse_asset, get_pulse_snapshot

        pulse_asset = brief_pulse_asset(want or brief.asset)
        if pulse_asset:
            brief = brief.model_copy(update={"pulse": get_pulse_snapshot(pulse_asset)})
    except Exception:
        pass
    return brief


@router.get("/inferences", response_model=list[StrategyInference])
def list_inferences(limit: int = Query(default=50, le=100)) -> list[StrategyInference]:
    return store.inferences[:limit]


@router.get("/inferences/{address}", response_model=StrategyInference | None)
def get_inference(address: str) -> StrategyInference | None:
    for item in store.inferences:
        if item.trader_address == address:
            return item
    return None


@router.get("/alerts", response_model=list[AlertHistoryItem])
def list_alerts(
    status: str | None = None,
    limit: int = Query(default=50, le=100),
) -> list[AlertHistoryItem]:
    results = store.alerts
    if status:
        results = [a for a in results if a.status == status]
    return results[:limit]


@router.get("/pipeline/status", response_model=PipelineStatus)
def pipeline_status() -> PipelineStatus:
    return store.pipeline_status()


@router.get("/fear-greed", response_model=FearGreedIndex | None)
async def fear_greed(force: bool = Query(default=False)) -> FearGreedIndex | None:
    """CMC Crypto Fear and Greed — external sentiment for contrast with Top3 whale bias."""
    from app.services.fear_greed import fetch_fear_greed

    return await fetch_fear_greed(force=force)


@router.get("/market/status", response_model=MarketStatus)
def market_status() -> MarketStatus:
    """Summarise recent Hyperliquid on-chain market activity."""
    now = datetime.now(timezone.utc)
    windows = rollup_liq_windows(now)
    w1 = windows.get("1h") or {}
    w4 = windows.get("4h") or {}
    w24 = windows.get("24h") or {}

    db: Session = SessionLocal()
    try:
        last_snapshot = (
            db.query(MarketSnapshotRow)
            .order_by(MarketSnapshotRow.timestamp.desc())
            .first()
        )
        last_liq = (
            db.query(LiquidationRow)
            .order_by(LiquidationRow.timestamp.desc())
            .first()
        )
    finally:
        db.close()

    has_live = last_snapshot is not None or last_liq is not None
    top_asset = last_snapshot.asset if last_snapshot is not None else None
    liq_24h_events = int(w24.get("events") or 0)

    return MarketStatus(
        top_asset=top_asset,
        last_snapshot_at=last_snapshot.timestamp if last_snapshot else None,
        last_liquidation_at=last_liq.timestamp if last_liq else None,
        liquidation_events_24h=liq_24h_events,
        has_live_market=has_live,
        liq_1h_long_usd=float(w1.get("long_usd") or 0),
        liq_1h_short_usd=float(w1.get("short_usd") or 0),
        liq_1h_total_usd=float(w1.get("total_usd") or 0),
        liq_1h_events=int(w1.get("events") or 0),
        liq_4h_long_usd=float(w4.get("long_usd") or 0),
        liq_4h_short_usd=float(w4.get("short_usd") or 0),
        liq_4h_total_usd=float(w4.get("total_usd") or 0),
        liq_4h_events=int(w4.get("events") or 0),
        liq_24h_long_usd=float(w24.get("long_usd") or 0),
        liq_24h_short_usd=float(w24.get("short_usd") or 0),
        liq_24h_total_usd=float(w24.get("total_usd") or 0),
        liq_24h_events=liq_24h_events,
        liq_1h_pressure=pressure_line(w1),
        liq_4h_pressure=pressure_line(w4),
        liq_24h_pressure=pressure_line(w24),
    )


@router.get("/whale-book/summary", response_model=WhaleBookSummary)
def whale_book_summary() -> WhaleBookSummary:
    if store.whale_summary:
        return store.whale_summary
    return summarize_whale_book(store.whale_positions, tracked=len(store.traders))


@router.get("/market/coin-pulse", response_model=list[CoinPulse])
def coin_pulse(
    assets: list[str] | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=40),
) -> list[CoinPulse]:
    """Live-ish coin board ranked by 24h notional volume (Hyperliquid dayNtlVlm)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    asset_filter = assets if isinstance(assets, list) else None
    row_limit = limit if isinstance(limit, int) else 12
    summary = store.whale_summary or summarize_whale_book(
        store.whale_positions, tracked=len(store.traders)
    )

    liq_usd: dict[str, dict[str, float]] = {}
    liq_counts: dict[str, dict[str, int]] = {}
    liq_events_by_asset: dict[str, list] = {}
    for event in store.liquidation_events:
        if event.timestamp < cutoff:
            continue
        usd_bucket = liq_usd.setdefault(event.asset, {"long": 0.0, "short": 0.0})
        count_bucket = liq_counts.setdefault(event.asset, {"long": 0, "short": 0})
        key = "long" if event.side.value == "long" else "short"
        usd_bucket[key] += float(event.size_usd)
        count_bucket[key] += 1
        liq_events_by_asset.setdefault(event.asset, []).append(event)

    ticks = dict(store.market_ticks)
    if not ticks:
        db: Session = SessionLocal()
        try:
            # Latest snapshot per asset from DB (fallback when collector just started).
            rows = (
                db.query(MarketSnapshotRow)
                .order_by(MarketSnapshotRow.timestamp.desc())
                .limit(2000)
                .all()
            )
            for row in rows:
                if row.asset in ticks:
                    continue
                prev = getattr(row, "prev_day_price", None)
                change = None
                if prev and prev > 0:
                    change = (float(row.mark_price) - float(prev)) / float(prev) * 100.0
                ticks[row.asset] = {
                    "asset": row.asset,
                    "mark_price": float(row.mark_price),
                    "open_interest": float(row.open_interest),
                    "funding_rate": float(row.funding_rate),
                    "day_volume_usd": float(getattr(row, "day_volume_usd", 0.0) or 0.0),
                    "prev_day_price": float(prev) if prev else None,
                    "change_pct_24h": round(change, 3) if change is not None else None,
                }
        finally:
            db.close()

    if asset_filter:
        wanted = {a.upper() for a in asset_filter}
        tick_list = [t for a, t in ticks.items() if a.upper() in wanted]
    else:
        tick_list = list(ticks.values())

    tick_list.sort(key=lambda t: float(t.get("day_volume_usd") or 0.0), reverse=True)
    if not tick_list and summary.by_asset:
        # Last resort: whale-book assets only (no live volume yet).
        tick_list = [
            {
                "asset": a.asset,
                "mark_price": None,
                "open_interest": None,
                "funding_rate": None,
                "day_volume_usd": abs(a.long_notional_usd) + abs(a.short_notional_usd),
                "change_pct_24h": None,
            }
            for a in sorted(
                summary.by_asset.values(),
                key=lambda x: x.long_notional_usd + x.short_notional_usd,
                reverse=True,
            )
        ]

    results: list[CoinPulse] = []
    enriched: list[tuple[dict, object | None, dict, dict, list[dict]]] = []
    for tick in tick_list[:row_limit]:
        asset = str(tick["asset"])
        asset_summary = summary.by_asset.get(asset)
        liq_u = liq_usd.get(asset, {"long": 0.0, "short": 0.0})
        liq_c = liq_counts.get(asset, {"long": 0, "short": 0})

        # 6 buckets over 24h for a tiny liq timeline (long vs short $).
        buckets = [{"long": 0.0, "short": 0.0} for _ in range(6)]
        for event in liq_events_by_asset.get(asset, []):
            age_h = (now - event.timestamp).total_seconds() / 3600.0
            idx = min(5, max(0, int(age_h // 4)))
            bucket_i = 5 - idx
            side_key = "long" if event.side.value == "long" else "short"
            buckets[bucket_i][side_key] += float(event.size_usd)

        enriched.append((tick, asset_summary, liq_u, liq_c, buckets))

    for tick, asset_summary, liq_u, liq_c, buckets in enriched:
        asset = str(tick["asset"])
        mark = tick.get("mark_price")
        oi_contracts = tick.get("open_interest")
        oi_usd = None
        if mark and oi_contracts is not None:
            try:
                oi_usd = float(mark) * float(oi_contracts)
            except (TypeError, ValueError):
                oi_usd = None
        whale_notional = 0.0
        if asset_summary:
            whale_notional = asset_summary.long_notional_usd + asset_summary.short_notional_usd
        whale_oi_pct = None
        if oi_usd and oi_usd > 0 and whale_notional > 0:
            whale_oi_pct = round(min(100.0, whale_notional / oi_usd * 100.0), 2)

        long_pct = asset_summary.long_pct if asset_summary else None
        results.append(
            CoinPulse(
                asset=asset,
                mark_price=mark,
                change_pct_24h=tick.get("change_pct_24h"),
                day_volume_usd=tick.get("day_volume_usd"),
                funding_rate=tick.get("funding_rate"),
                open_interest=oi_contracts,
                open_interest_usd=round(oi_usd, 2) if oi_usd is not None else None,
                whale_long_pct=long_pct,
                whale_net_notional_usd=(
                    asset_summary.net_notional_usd if asset_summary else None
                ),
                whale_positioned=asset_summary.whales if asset_summary else 0,
                whale_avg_leverage=(
                    asset_summary.avg_leverage if asset_summary else None
                ),
                whale_bias_label=whale_bias_label(long_pct),
                whale_oi_pct=whale_oi_pct,
                asset_tag=asset_market_tag(asset),
                liq_long_usd_24h=round(liq_u["long"], 2),
                liq_short_usd_24h=round(liq_u["short"], 2),
                liq_long_24h=liq_c["long"],
                liq_short_24h=liq_c["short"],
                liq_timeline=buckets,
            )
        )
    return results


@router.get("/whale-book/biggest-positions", response_model=list[BiggestPosition])
def biggest_positions(
    limit: int = Query(default=8, ge=1, le=25),
) -> list[BiggestPosition]:
    """BL-04: largest tracked-whale open positions by notional."""
    row_limit = limit if isinstance(limit, int) else 8
    traders_by_addr = {t.address: t.alias for t in store.traders}
    marks: dict[str, float] = {}
    for asset, tick in (store.market_ticks or {}).items():
        mark = tick.get("mark_price")
        if mark is not None:
            try:
                marks[asset] = float(mark)
            except (TypeError, ValueError):
                pass
    return list_biggest_positions(
        store.whale_positions,
        traders_by_addr=traders_by_addr,
        marks=marks,
        limit=row_limit,
    )


@router.get("/whale-book/cohort-bias", response_model=CohortBiasResponse)
def whale_book_cohort_bias(
    assets: list[str] | None = Query(default=None),
    smart_n: int = Query(default=SMART_MONEY_SIZE, ge=3, le=50),
    limit: int = Query(default=5, ge=2, le=10),
    include_thin: bool = Query(default=False),
) -> CohortBiasResponse:
    """BL-06/07: Smart Money top-N vs rest of tracked book, per coin.

    `include_thin` appends low-liquidity names that tracked whales still hold,
    which is what the Insights heatmap renders.
    """
    return compute_cohort_bias(
        assets=assets,
        smart_n=smart_n,
        limit=limit,
        include_thin=include_thin,
    )


@router.get("/traders/{address}/fills", response_model=TraderFillsSummary | None)
async def trader_recent_fills(
    address: str,
    hours: int = Query(default=24, ge=1, le=48),
) -> TraderFillsSummary | None:
    """BL-09: last-24h executed flow for one tracked trader."""
    return await fetch_recent_fills(address, window_hours=hours)


@router.get("/whale-book/liq-proximity", response_model=list[LiqProximityRow])
def whale_book_liq_proximity(
    limit: int = Query(default=10, ge=1, le=25),
) -> list[LiqProximityRow]:
    """BL-12: tracked positions closest to liquidation (distance%)."""
    return list_liq_proximity(limit=limit)


@router.get("/market/pulse", response_model=MarketPulse)
def market_pulse(
    top_n: int = Query(default=20, ge=3, le=40),
) -> MarketPulse:
    """BL-10: market-wide OI / Vol / Liq(24h) strip with short deltas."""
    return compute_market_pulse(top_n=top_n)


@router.post("/pipeline/run", response_model=PipelineStatus)
async def run_pipeline_now() -> PipelineStatus:
    from app.collectors.hyperliquid import collect_market_snapshot

    await collect_market_snapshot()
    results = await run_inference_pipeline()
    run_ranking_pipeline()
    await process_alert_triggers(
        whale_alerts=store.whale_alerts[:3],
        zones=[z for z in store.liquidation_zones if z.size_usd >= 100_000_000][:2],
        inferences=results,
    )
    return store.pipeline_status()
