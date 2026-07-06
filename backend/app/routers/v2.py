from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.orm import LiquidationRow, MarketSnapshotRow
from app.models.schemas import (
    AlertHistoryItem,
    CoinPulse,
    MarketInsight,
    MarketStatus,
    PipelineStatus,
    SmartMoneyRank,
    StrategyInference,
    WhaleBookSummary,
)
from app.services.alerts import process_alert_triggers
from app.services.inference import run_inference_pipeline
from app.services.ranking import run_ranking_pipeline
from app.services.store import store
from app.services.whale_book import summarize_whale_book

router = APIRouter(prefix="/api/v2", tags=["v2"])


@router.get("/rankings", response_model=list[SmartMoneyRank])
def list_rankings(limit: int = Query(default=50, le=100)) -> list[SmartMoneyRank]:
    if not store.rankings:
        run_ranking_pipeline()
    return store.rankings[:limit]


@router.get("/insights", response_model=list[MarketInsight])
def list_insights(limit: int = Query(default=20, le=50)) -> list[MarketInsight]:
    return store.insights[:limit]


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


@router.get("/market/status", response_model=MarketStatus)
def market_status() -> MarketStatus:
    """Summarise recent Hyperliquid on-chain market activity."""
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

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        liq_24h = (
            db.query(LiquidationRow)
            .filter(LiquidationRow.timestamp >= cutoff)
            .count()
        )
    finally:
        db.close()

    has_live = last_snapshot is not None or last_liq is not None
    top_asset = last_snapshot.asset if last_snapshot is not None else None

    return MarketStatus(
        top_asset=top_asset,
        last_snapshot_at=last_snapshot.timestamp if last_snapshot else None,
        last_liquidation_at=last_liq.timestamp if last_liq else None,
        liquidation_events_24h=liq_24h,
        has_live_market=has_live,
    )


@router.get("/whale-book/summary", response_model=WhaleBookSummary)
def whale_book_summary() -> WhaleBookSummary:
    if store.whale_summary:
        return store.whale_summary
    return summarize_whale_book(store.whale_positions, tracked=len(store.traders))


@router.get("/market/coin-pulse", response_model=list[CoinPulse])
def coin_pulse(
    assets: list[str] | None = Query(default=None),
) -> list[CoinPulse]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    summary = store.whale_summary or summarize_whale_book(store.whale_positions, tracked=len(store.traders))

    entries: dict[str, dict[str, int]] = {}
    exits: dict[str, dict[str, int]] = {}
    for alert in store.whale_alerts:
        if alert.timestamp < cutoff:
            continue
        bucket = entries if alert.alert_type.value == "entry" else exits
        asset_bucket = bucket.setdefault(alert.asset, {"long": 0, "short": 0})
        key = "long" if alert.side.value == "long" else "short"
        asset_bucket[key] += 1

    liq_counts: dict[str, dict[str, int]] = {}
    for event in store.liquidation_events:
        if event.timestamp < cutoff:
            continue
        asset_bucket = liq_counts.setdefault(event.asset, {"long": 0, "short": 0})
        key = "long" if event.side.value == "long" else "short"
        asset_bucket[key] += 1

    assets_set = set(assets or [])
    if not assets_set:
        assets_set.update(summary.by_asset.keys())
        assets_set.update({z.asset for z in store.liquidation_zones})
        assets_set.update({e.asset for e in store.liquidation_events})

    if not assets_set:
        return []

    db: Session = SessionLocal()
    try:
        snapshots: dict[str, MarketSnapshotRow] = {}
        for asset in assets_set:
            row = (
                db.query(MarketSnapshotRow)
                .filter(MarketSnapshotRow.asset == asset)
                .order_by(MarketSnapshotRow.timestamp.desc())
                .first()
            )
            if row:
                snapshots[asset] = row
    finally:
        db.close()

    results: list[CoinPulse] = []
    for asset in sorted(assets_set):
        asset_summary = summary.by_asset.get(asset)
        entry = entries.get(asset, {"long": 0, "short": 0})
        exit_counts = exits.get(asset, {"long": 0, "short": 0})
        liq = liq_counts.get(asset, {"long": 0, "short": 0})
        snapshot = snapshots.get(asset)
        results.append(
            CoinPulse(
                asset=asset,
                whale_long_pct=asset_summary.long_pct if asset_summary else 0.0,
                whale_net_notional_usd=asset_summary.net_notional_usd if asset_summary else 0.0,
                whale_positioned=asset_summary.whales if asset_summary else 0,
                entries_long_24h=entry["long"],
                entries_short_24h=entry["short"],
                exits_long_24h=exit_counts["long"],
                exits_short_24h=exit_counts["short"],
                liq_long_24h=liq["long"],
                liq_short_24h=liq["short"],
                funding_rate=float(snapshot.funding_rate) if snapshot else None,
                open_interest=float(snapshot.open_interest) if snapshot else None,
                mark_price=float(snapshot.mark_price) if snapshot else None,
            )
        )
    return results

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
