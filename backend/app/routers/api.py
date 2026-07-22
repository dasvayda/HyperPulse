from fastapi import APIRouter, HTTPException, Query

from app.collectors.whales import fetch_live_open_positions
from app.models.schemas import (
    DashboardStats,
    LiquidationEvent,
    LiquidationZone,
    TraderDetail,
    TraderProfile,
    WhaleAlert,
)
from app.services.store import store

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats() -> DashboardStats:
    return store.refresh_dashboard()


@router.get("/whale-alerts", response_model=list[WhaleAlert])
def list_whale_alerts(
    asset: str | None = None,
    alert_type: str | None = None,
    limit: int = Query(default=50, le=100),
) -> list[WhaleAlert]:
    results = store.whale_alerts
    if asset:
        results = [a for a in results if a.asset.lower() == asset.lower()]
    if alert_type:
        results = [a for a in results if a.alert_type.value == alert_type.lower()]
    return results[:limit]


@router.get("/traders", response_model=list[TraderProfile])
def list_traders(
    limit: int = Query(default=50, le=100),
) -> list[TraderProfile]:
    return store.traders[:limit]


@router.get("/traders/{address}", response_model=TraderDetail)
async def get_trader(address: str) -> TraderDetail:
    live_positions = await fetch_live_open_positions(address)
    trader = store.get_trader_detail(address, open_positions=live_positions)
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    return trader


@router.get("/liquidations/zones", response_model=list[LiquidationZone])
def list_liquidation_zones(
    asset: str | None = None,
) -> list[LiquidationZone]:
    if asset:
        return [z for z in store.liquidation_zones if z.asset.lower() == asset.lower()]
    return store.liquidation_zones


@router.get("/liquidations/events", response_model=list[LiquidationEvent])
def list_liquidation_events(
    asset: str | None = None,
    limit: int = Query(default=50, le=100),
) -> list[LiquidationEvent]:
    results = store.liquidation_events
    if asset:
        results = [e for e in results if e.asset.lower() == asset.lower()]
    return results[:limit]
