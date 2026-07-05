from fastapi import APIRouter, HTTPException

from app.collectors.hyperliquid_client import info as hl_info
from app.models.schemas import MarketInsight, StrategyInference, TraderDetail
from app.services.inference import run_inference_pipeline
from app.services.store import store

router = APIRouter(prefix="/api/v3", tags=["v3"])


@router.get("/portfolio/{address}", response_model=TraderDetail)
async def portfolio(address: str) -> TraderDetail:
    """Return a simple portfolio view backed by current trader detail."""
    detail = store.get_trader_detail(address)
    if not detail:
        raise HTTPException(status_code=404, detail="Trader not found")
    return detail


@router.get("/coach/{address}", response_model=StrategyInference | None)
async def coach_insight(address: str) -> StrategyInference | None:
    """Return latest strategy inference for a trader (acting as 'AI coach' summary)."""
    for item in store.inferences:
        if item.trader_address == address:
            return item
    # Fallback: trigger a one-off inference run.
    await run_inference_pipeline()
    for item in store.inferences:
        if item.trader_address == address:
            return item
    return None


@router.get("/signals", response_model=list[MarketInsight])
async def signals() -> list[MarketInsight]:
    """Expose current market insights as predictive signals."""
    # Reuse existing MarketInsight objects as the Phase 3 'signals' surface.
    return store.insights

