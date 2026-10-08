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


class AlertExecutionEvidence(BaseModel):
    """Executed-fill evidence reconciled against a whale position change."""

    verified: bool = False
    fill_count: int = 0
    notional_usd: float = 0.0
    quantity: float = 0.0
    price_low: float | None = None
    price_high: float | None = None
    tx_hashes: list[str] = Field(default_factory=list)


class WhaleAlert(BaseModel):
    id: str
    trader_address: str
    trader_alias: str
    asset: str
    side: PositionSide
    alert_type: AlertType
    size_usd: float
    size_delta_usd: float | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    mark_price: float | None = None
    unrealized_pnl_usd: float | None = None
    roi_pct: float | None = None
    whale_long_pct: float | None = None
    leverage: float
    win_rate: float
    inferred_strategy: str
    confidence_score: float = Field(ge=0, le=100)
    timestamp: datetime
    execution: AlertExecutionEvidence | None = None


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


class WhalePosition(BaseModel):
    trader_address: str
    asset: str
    side: PositionSide
    size_usd: float
    entry_price: float
    leverage: float
    liquidation_px: float | None = None


class OpenPosition(BaseModel):
    asset: str
    side: PositionSide
    size_usd: float
    entry_price: float
    leverage: float
    mark_price: float | None = None
    roi_pct: float | None = None
    unrealized_pnl_usd: float | None = None
    liquidation_px: float | None = None
    liq_distance_pct: float | None = None


class CopyVerdict(BaseModel):
    """BL-08 due-diligence label for copy / follow decisions."""

    verdict: str  # watch | caution | skip
    reasons: list[str] = Field(default_factory=list)


class TraderFillAsset(BaseModel):
    asset: str
    buy_usd: float = 0.0
    sell_usd: float = 0.0
    net_usd: float = 0.0
    fills: int = 0


class TraderFillsSummary(BaseModel):
    """BL-09: last-24h executed flow for one tracked trader (userFillsByTime)."""

    window_hours: int = 24
    fills: int = 0
    buy_usd: float = 0.0
    sell_usd: float = 0.0
    net_usd: float = 0.0
    realized_pnl_usd: float = 0.0
    assets: list[TraderFillAsset] = Field(default_factory=list)
    top_asset: str | None = None
    last_fill_at: datetime | None = None
    position_check: str | None = None


class TraderDetail(TraderProfile):
    recent_positions: list[dict]
    open_positions: list[OpenPosition] = []
    behavior_summary: str
    inferred_strategy: str | None = None
    inferred_trading_style: str | None = None
    inference_confidence: float | None = None
    smart_money_score: float | None = None
    open_roi_pct: float | None = None
    open_unrealized_pnl_usd: float | None = None
    avg_leverage: float | None = None
    max_leverage: float | None = None
    copy_verdict: str | None = None
    copy_reasons: list[str] = Field(default_factory=list)
    recent_fills: TraderFillsSummary | None = None


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
    long_whale_count: int = 0
    short_whale_count: int = 0
    neutral_whale_count: int = 0
    whale_count_long_pct: float = 0.0
    updated_at: datetime
    by_asset: dict[str, AssetWhaleSummary]


class CoinPulse(BaseModel):
    asset: str
    mark_price: float | None = None
    change_pct_24h: float | None = None
    day_volume_usd: float | None = None
    funding_rate: float | None = None
    open_interest: float | None = None
    open_interest_usd: float | None = None
    whale_long_pct: float | None = None
    whale_net_notional_usd: float | None = None
    whale_positioned: int = 0
    whale_avg_leverage: float | None = None
    whale_bias_label: str | None = None
    whale_oi_pct: float | None = None
    asset_tag: str | None = None
    liq_long_usd_24h: float = 0.0
    liq_short_usd_24h: float = 0.0
    liq_long_24h: int = 0
    liq_short_24h: int = 0
    liq_timeline: list[dict] = []
    # Legacy fields kept optional so older clients do not break.
    entries_long_24h: int = 0
    entries_short_24h: int = 0
    exits_long_24h: int = 0
    exits_short_24h: int = 0


class BiggestPosition(BaseModel):
    rank: int
    trader_address: str
    trader_alias: str
    asset: str
    side: PositionSide
    size_usd: float
    entry_price: float
    leverage: float
    mark_price: float | None = None
    roi_pct: float | None = None
    unrealized_pnl_usd: float | None = None
    liquidation_px: float | None = None
    liq_distance_pct: float | None = None


class CohortBiasAsset(BaseModel):
    asset: str
    smart_long_pct: float | None = None
    rest_long_pct: float | None = None
    delta_pp: float | None = None
    smart_notional_usd: float = 0.0
    rest_notional_usd: float = 0.0
    smart_whales: int = 0
    rest_whales: int = 0
    # BL-07 heatmap context: whole tracked book + how thin the market is.
    all_long_pct: float | None = None
    whale_oi_pct: float | None = None
    day_volume_usd: float | None = None
    thin: bool = False


class CohortBiasResponse(BaseModel):
    assets: list[CohortBiasAsset]
    smart_n: int
    updated_at: datetime


class LiqProximityRow(BaseModel):
    rank: int
    trader_address: str
    trader_alias: str
    asset: str
    side: PositionSide
    size_usd: float
    leverage: float
    mark_price: float
    liquidation_px: float
    distance_pct: float
    source: str = "liquidationPx"  # liquidationPx | estimate


class MarketPulse(BaseModel):
    oi_usd: float = 0.0
    oi_delta_pct: float | None = None
    vol_usd_24h: float = 0.0
    vol_delta_pct: float | None = None
    liq_usd_24h: float = 0.0
    liq_delta_pct: float | None = None
    scope: str = "top20"
    as_of: datetime


class FearGreedIndex(BaseModel):
    """CMC Crypto Fear and Greed (external sentiment; contrast with HL whale bias)."""

    value: int = Field(ge=0, le=100)
    classification: str
    as_of: datetime
    yesterday_value: int | None = None
    yesterday_classification: str | None = None
    source: str = "cmc"
    positive: bool | None = None


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
    account_value_usd: float = 0.0
    win_rate: float = 0.0
    pnl_change_pct: float
    open_roi_pct: float | None = None
    open_unrealized_pnl_usd: float | None = None
    strategy_tags: list[str]
    inferred_strategy: str | None = None
    risk_score: float
    momentum_score: float
    consistency_score: float
    sparkline: list[float]


class PerformanceRankingResponse(BaseModel):
    """Open ROI / PnL ranking with an auto-tuned eligibility threshold."""

    threshold_usd: float
    target_count: int
    base_threshold_usd: float
    items: list[SmartMoneyRank]


class InsightStance(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class PulseDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    WAIT = "wait"


class PulseStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    STALE = "stale"


class PulseTick(BaseModel):
    direction: PulseDirection
    hit: bool | None = None
    created_at: datetime


class PulseSnapshot(BaseModel):
    """Short-horizon direction probabilities (separate from rule-vote confidence)."""

    asset: str
    horizon_sec: int = 900
    direction: PulseDirection
    p_up: float = Field(ge=0, le=1)
    p_down: float = Field(ge=0, le=1)
    p_wait: float = Field(ge=0, le=1)
    as_of: datetime
    due_at: datetime
    status: PulseStatus = PulseStatus.OPEN
    ticks: list[PulseTick] = Field(default_factory=list)
    hit_rate: float | None = None
    hit_n: int = 0
    warming_up: bool = True


class MarketInsight(BaseModel):
    id: str
    title: str
    summary: str
    asset: str | None = None
    stance: InsightStance = InsightStance.HOLD
    confidence: float = Field(ge=0, le=100)
    signals: list[str]
    created_at: datetime
    pulse: PulseSnapshot | None = None


class AlertHistoryItem(BaseModel):
    id: str
    channel: str
    event_type: str
    title: str
    message: str
    status: str
    created_at: datetime
    sent_at: datetime | None = None


class AlertDeliverySummary(BaseModel):
    window_hours: int = 24
    sent: int = 0
    failed: int = 0
    queued: int = 0
    attempted: int = 0
    delivery_rate_pct: float | None = None
    last_sent_at: datetime | None = None
    last_failed_at: datetime | None = None


class CollectorStatus(BaseModel):
    status: str
    last_success_at: datetime | None = None
    checked_at: datetime
    successful: int
    expected: int


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
    collectors: dict[str, CollectorStatus] = Field(default_factory=dict)


class ReadinessComponent(BaseModel):
    """One operational dependency, reported independently in readiness."""

    status: str
    detail: str
    checked_at: datetime
    last_success_at: datetime | None = None


class ReadinessStatus(BaseModel):
    status: str
    database: ReadinessComponent
    cache: ReadinessComponent
    collector: ReadinessComponent


class MarketStatus(BaseModel):
    top_asset: str | None = None
    last_snapshot_at: datetime | None
    last_liquidation_at: datetime | None
    liquidation_events_24h: int
    has_live_market: bool
    # BL-03 A: last-1h rollup across tracked markets (recentTrades).
    liq_1h_long_usd: float = 0.0
    liq_1h_short_usd: float = 0.0
    liq_1h_total_usd: float = 0.0
    liq_1h_events: int = 0
    liq_4h_long_usd: float = 0.0
    liq_4h_short_usd: float = 0.0
    liq_4h_total_usd: float = 0.0
    liq_4h_events: int = 0
    liq_24h_long_usd: float = 0.0
    liq_24h_short_usd: float = 0.0
    liq_24h_total_usd: float = 0.0
    liq_24h_events: int = 0
    liq_1h_pressure: str = ""
    liq_4h_pressure: str = ""
    liq_24h_pressure: str = ""


class BriefStance(str, Enum):
    PREFER_LONG = "prefer_long"
    PREFER_SHORT = "prefer_short"
    WAIT = "wait"


class BriefTldr(BaseModel):
    now: str
    short_read: str
    however: str


class BriefDigest(BaseModel):
    """Labeled Market Brief body shared by Telegram and Insights."""

    as_of_line: str
    funding_line: str = ""
    positioning: list[str] = Field(default_factory=list)
    read: str = ""
    note: str = ""
    coverage_band: str = "Low"


class MarketBrief(BaseModel):
    """Desk-style market commentary built from a structured HL snapshot."""

    headline: str
    market_status: str
    stance: BriefStance = BriefStance.WAIT
    suggestions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    tldr: BriefTldr | None = None
    digest: BriefDigest | None = None
    asset: str | None = None
    stale: bool = False
    tab_assets: list[str] = Field(default_factory=list)
    as_of: datetime
    provider: str = "template"
    source: str = "template"  # llm | template
    snapshot_hash: str = ""
    pulse: PulseSnapshot | None = None


class PaperPortfolioPosition(BaseModel):
    asset: str
    direction: str
    quantity: float
    average_entry: float
    mark_price: float | None = None
    notional_usd: float
    unrealized_pnl_usd: float
    weight_pct: float
    updated_at: datetime


class PaperPortfolioTrade(BaseModel):
    id: str
    asset: str
    side: str
    action: str
    quantity: float
    mark_price: float
    fill_price: float
    notional_usd: float
    fee_usd: float
    slippage_usd: float
    realized_pnl_usd: float
    created_at: datetime


class PaperEquityPoint(BaseModel):
    nav: float
    benchmark_nav: float | None = None
    drawdown_pct: float
    created_at: datetime


class PaperPortfolioSummary(BaseModel):
    strategy_id: str
    version: str
    status: str
    initial_cash: float
    nav: float
    return_pct: float
    benchmark_nav: float | None = None
    benchmark_return_pct: float | None = None
    max_drawdown_pct: float
    cash: float
    gross_exposure_usd: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    cumulative_fees: float
    cumulative_slippage: float
    cumulative_funding: float
    trades_count: int
    closed_trades_count: int
    win_rate: float | None = None
    current_positions: list[PaperPortfolioPosition] = Field(default_factory=list)
    last_decisions: list[dict] = Field(default_factory=list)
    started_at: datetime
    updated_at: datetime
    warming_up: bool = True
    disclosure: str


class PaperStrategyDetail(BaseModel):
    strategy_id: str
    version: str
    status: str
    config_hash: str
    config: dict
    started_at: datetime
