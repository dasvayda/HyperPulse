from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AlertType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class LiquidationSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class WhaleAlert(BaseModel):
    id: str
    trader_address: str
    trader_alias: str
    asset: str
    side: PositionSide
    alert_type: AlertType
    size_usd: float
    entry_price: float | None = None
    exit_price: float | None = None
    leverage: float
    win_rate: float
    inferred_strategy: str
    confidence_score: float = Field(ge=0, le=100)
    timestamp: datetime


class TraderProfile(BaseModel):
    address: str
    alias: str
    rank: int
    pnl_usd: float
    pnl_change_pct: float
    account_value_usd: float = 0.0
    volume_usd: float = 0.0
    win_rate: float
    avg_hold_hours: float
    total_trades: int
    preferred_assets: list[str]
    strategy_tags: list[str]
    risk_score: float = Field(ge=0, le=100)
    sparkline: list[float]


class TraderDetail(TraderProfile):
    recent_positions: list[dict]
    behavior_summary: str


class LiquidationZone(BaseModel):
    id: str
    asset: str
    price: float
    side: LiquidationSide
    size_usd: float
    distance_pct: float
    open_interest_pct: float
    sparkline: list[float]


class LiquidationEvent(BaseModel):
    id: str
    asset: str
    side: LiquidationSide
    size_usd: float
    price: float
    timestamp: datetime
    tx_hash: str | None = None


class WhalePosition(BaseModel):
    trader_address: str
    asset: str
    side: PositionSide
    size_usd: float
    entry_price: float
    leverage: float


class AssetWhaleSummary(BaseModel):
    asset: str
    whales: int
    long_notional_usd: float
    short_notional_usd: float
    long_pct: float
    net_notional_usd: float
    net_bias: str
    avg_leverage: float


class WhaleBookSummary(BaseModel):
    tracked: int
    with_positions: int
    long_notional_usd: float
    short_notional_usd: float
    long_pct: float
    net_notional_usd: float
    net_bias: str
    updated_at: datetime
    by_asset: dict[str, AssetWhaleSummary]


class CoinPulse(BaseModel):
    asset: str
    whale_long_pct: float
    whale_net_notional_usd: float
    whale_positioned: int
    entries_long_24h: int
    entries_short_24h: int
    exits_long_24h: int
    exits_short_24h: int
    liq_long_24h: int
    liq_short_24h: int
    funding_rate: float | None = None
    open_interest: float | None = None
    mark_price: float | None = None


class DashboardStats(BaseModel):
    active_whales: int
    alerts_24h: int
    total_liquidations_24h: float
    top_asset: str
    whales_positioned: int | None = None
    whale_long_pct: float | None = None
    whale_net_bias: str | None = None
    dominant_strategy: str | None = None
    avg_smart_money_score: float | None = None
    telegram_alerts_24h: int | None = None
    data_source: str | None = None


class StrategyInference(BaseModel):
    id: str
    trader_address: str
    trader_alias: str
    strategy: str
    trading_style: str
    risk_profile: str
    confidence: float = Field(ge=0, le=100)
    rationale: str
    provider: str
    created_at: datetime


class SmartMoneyRank(BaseModel):
    address: str
    alias: str
    rank: int
    smart_money_score: float
    pnl_usd: float
    win_rate: float
    pnl_change_pct: float
    strategy_tags: list[str]
    risk_score: float
    momentum_score: float
    consistency_score: float
    sparkline: list[float]


class MarketInsight(BaseModel):
    id: str
    title: str
    summary: str
    asset: str | None = None
    confidence: float = Field(ge=0, le=100)
    signals: list[str]
    created_at: datetime


class AlertHistoryItem(BaseModel):
    id: str
    channel: str
    event_type: str
    title: str
    message: str
    status: str
    created_at: datetime
    sent_at: datetime | None = None


class PipelineStatus(BaseModel):
    collector_enabled: bool
    last_collect_at: datetime | None
    last_inference_at: datetime | None
    last_ranking_at: datetime | None
    last_alert_at: datetime | None
    telegram_configured: bool
    ai_provider: str
    traders_tracked: int
    inferences_count: int
    alerts_count: int
    data_source: str


class MarketStatus(BaseModel):
    top_asset: str | None = None
    last_snapshot_at: datetime | None
    last_liquidation_at: datetime | None
    liquidation_events_24h: int
    has_live_market: bool
