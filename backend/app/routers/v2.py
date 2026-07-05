from fastapi import APIRouter, Query

from app.models.schemas import (
    AlertHistoryItem,
    MarketInsight,
    PipelineStatus,
    SmartMoneyRank,
    StrategyInference,
)
from app.services.alerts import process_alert_triggers
from app.services.inference import run_inference_pipeline
from app.services.ranking import run_ranking_pipeline
from app.services.store import store

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
