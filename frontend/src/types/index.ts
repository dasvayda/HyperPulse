export type PositionSide = "long" | "short";
export type AlertType = "entry" | "exit";
export type LiquidationSide = "long" | "short";

export interface WhaleAlert {
  id: string;
  trader_address: string;
  trader_alias: string;
  asset: string;
  side: PositionSide;
  alert_type: AlertType;
  size_usd: number;
  size_delta_usd?: number | null;
  entry_price: number | null;
  exit_price: number | null;
  mark_price?: number | null;
  unrealized_pnl_usd?: number | null;
  roi_pct?: number | null;
  whale_long_pct?: number | null;
  leverage: number;
  win_rate: number;
  inferred_strategy: string;
  confidence_score: number;
  timestamp: string;
}

export interface TraderProfile {
  address: string;
  alias: string;
  rank: number;
  pnl_usd: number;
  pnl_change_pct: number;
  account_value_usd?: number;
  volume_usd?: number;
  win_rate: number;
  avg_hold_hours: number;
  total_trades: number;
  preferred_assets: string[];
  strategy_tags: string[];
  risk_score: number;
  sparkline: number[];
}

export interface OpenPosition {
  asset: string;
  side: PositionSide;
  size_usd: number;
  entry_price: number;
  leverage: number;
  mark_price?: number | null;
  roi_pct?: number | null;
  unrealized_pnl_usd?: number | null;
  liquidation_px?: number | null;
  liq_distance_pct?: number | null;
}

export interface TraderFillAsset {
  asset: string;
  buy_usd: number;
  sell_usd: number;
  net_usd: number;
  fills: number;
}

export interface TraderFillsSummary {
  window_hours: number;
  fills: number;
  buy_usd: number;
  sell_usd: number;
  net_usd: number;
  realized_pnl_usd: number;
  assets: TraderFillAsset[];
  top_asset?: string | null;
  last_fill_at?: string | null;
  position_check?: string | null;
}

export interface TraderDetail extends TraderProfile {
  recent_positions: {
    asset: string;
    side: string;
    type: string;
    size_usd: number;
    price: number | null;
    timestamp: string;
  }[];
  open_positions?: OpenPosition[];
  behavior_summary: string;
  inferred_strategy?: string | null;
  inferred_trading_style?: string | null;
  inference_confidence?: number | null;
  smart_money_score?: number | null;
  open_roi_pct?: number | null;
  open_unrealized_pnl_usd?: number | null;
  avg_leverage?: number | null;
  max_leverage?: number | null;
  copy_verdict?: "watch" | "caution" | "skip" | string | null;
  copy_reasons?: string[];
  recent_fills?: TraderFillsSummary | null;
}

export interface LiquidationZone {
  id: string;
  asset: string;
  price: number;
  side: LiquidationSide;
  size_usd: number;
  distance_pct: number;
  open_interest_pct: number;
  sparkline: number[];
}

export interface LiquidationEvent {
  id: string;
  asset: string;
  side: LiquidationSide;
  size_usd: number;
  price: number;
  timestamp: string;
  tx_hash?: string | null;
}

export interface AssetWhaleSummary {
  asset: string;
  whales: number;
  long_notional_usd: number;
  short_notional_usd: number;
  long_pct: number;
  net_notional_usd: number;
  net_bias: string;
  avg_leverage: number;
}

export interface WhaleBookSummary {
  tracked: number;
  with_positions: number;
  long_notional_usd: number;
  short_notional_usd: number;
  long_pct: number;
  net_notional_usd: number;
  net_bias: string;
  long_whale_count: number;
  short_whale_count: number;
  neutral_whale_count: number;
  whale_count_long_pct: number;
  updated_at: string;
  by_asset: Record<string, AssetWhaleSummary>;
}

export interface CoinPulse {
  asset: string;
  mark_price?: number | null;
  change_pct_24h?: number | null;
  day_volume_usd?: number | null;
  funding_rate?: number | null;
  open_interest?: number | null;
  open_interest_usd?: number | null;
  whale_long_pct?: number | null;
  whale_net_notional_usd?: number | null;
  whale_positioned?: number;
  whale_avg_leverage?: number | null;
  whale_bias_label?: string | null;
  whale_oi_pct?: number | null;
  asset_tag?: string | null;
  liq_long_usd_24h?: number;
  liq_short_usd_24h?: number;
  liq_long_24h?: number;
  liq_short_24h?: number;
  liq_timeline?: { long: number; short: number }[];
  entries_long_24h?: number;
  entries_short_24h?: number;
  exits_long_24h?: number;
  exits_short_24h?: number;
}

export interface BiggestPosition {
  rank: number;
  trader_address: string;
  trader_alias: string;
  asset: string;
  side: PositionSide;
  size_usd: number;
  entry_price: number;
  leverage: number;
  mark_price?: number | null;
  roi_pct?: number | null;
  unrealized_pnl_usd?: number | null;
  liquidation_px?: number | null;
  liq_distance_pct?: number | null;
}

export interface CohortBiasAsset {
  asset: string;
  smart_long_pct?: number | null;
  rest_long_pct?: number | null;
  delta_pp?: number | null;
  smart_notional_usd: number;
  rest_notional_usd: number;
  smart_whales: number;
  rest_whales: number;
  all_long_pct?: number | null;
  whale_oi_pct?: number | null;
  day_volume_usd?: number | null;
  thin?: boolean;
}

export interface CohortBiasResponse {
  assets: CohortBiasAsset[];
  smart_n: number;
  updated_at: string;
}

export interface LiqProximityRow {
  rank: number;
  trader_address: string;
  trader_alias: string;
  asset: string;
  side: PositionSide;
  size_usd: number;
  leverage: number;
  mark_price: number;
  liquidation_px: number;
  distance_pct: number;
  source: string;
}

export interface MarketPulse {
  oi_usd: number;
  oi_delta_pct?: number | null;
  vol_usd_24h: number;
  vol_delta_pct?: number | null;
  liq_usd_24h: number;
  liq_delta_pct?: number | null;
  scope: string;
  as_of: string;
}

export interface FearGreedIndex {
  value: number;
  classification: string;
  as_of: string;
  yesterday_value?: number | null;
  yesterday_classification?: string | null;
  source: string;
  positive?: boolean | null;
}

export interface DashboardStats {
  active_whales: number;
  alerts_24h: number;
  total_liquidations_24h: number;
  top_asset: string;
  whales_positioned?: number | null;
  whale_long_pct?: number | null;
  whale_net_bias?: string | null;
  dominant_strategy?: string | null;
  avg_smart_money_score?: number | null;
  telegram_alerts_24h?: number | null;
  data_source?: string | null;
}

export interface StrategyInference {
  id: string;
  trader_address: string;
  trader_alias: string;
  strategy: string;
  trading_style: string;
  risk_profile: string;
  confidence: number;
  rationale: string;
  provider: string;
  created_at: string;
}

export interface SmartMoneyRank {
  address: string;
  alias: string;
  rank: number;
  smart_money_score: number;
  pnl_usd: number;
  account_value_usd?: number;
  win_rate: number;
  pnl_change_pct: number;
  strategy_tags: string[];
  inferred_strategy?: string | null;
  open_roi_pct?: number | null;
  open_unrealized_pnl_usd?: number | null;
  risk_score: number;
  momentum_score: number;
  consistency_score: number;
  sparkline: number[];
}

export interface PerformanceRankingResponse {
  threshold_usd: number;
  target_count: number;
  base_threshold_usd: number;
  items: SmartMoneyRank[];
}

export type InsightStance = "buy" | "sell" | "hold";

export type PulseDirection = "up" | "down" | "wait";
export type PulseStatus = "open" | "resolved" | "stale";

export interface PulseTick {
  direction: PulseDirection;
  hit: boolean | null;
  created_at: string;
}

export interface PulseSnapshot {
  asset: string;
  horizon_sec: number;
  direction: PulseDirection;
  p_up: number;
  p_down: number;
  p_wait: number;
  as_of: string;
  due_at: string;
  status: PulseStatus;
  ticks: PulseTick[];
  hit_rate: number | null;
  hit_n: number;
  warming_up: boolean;
}

export interface MarketInsight {
  id: string;
  title: string;
  summary: string;
  asset: string | null;
  stance: InsightStance;
  confidence: number;
  signals: string[];
  created_at: string;
  pulse?: PulseSnapshot | null;
}

export interface AlertHistoryItem {
  id: string;
  channel: string;
  event_type: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
  sent_at: string | null;
}

export interface PipelineStatus {
  collector_enabled: boolean;
  last_collect_at: string | null;
  last_inference_at: string | null;
  last_ranking_at: string | null;
  last_alert_at: string | null;
  telegram_configured: boolean;
  ai_provider: string;
  traders_tracked: number;
  inferences_count: number;
  alerts_count: number;
  data_source: string;
}

export interface MarketStatus {
  top_asset: string | null;
  last_snapshot_at: string | null;
  last_liquidation_at: string | null;
  liquidation_events_24h: number;
  has_live_market: boolean;
  liq_1h_long_usd?: number;
  liq_1h_short_usd?: number;
  liq_1h_total_usd?: number;
  liq_1h_events?: number;
  liq_4h_long_usd?: number;
  liq_4h_short_usd?: number;
  liq_4h_total_usd?: number;
  liq_4h_events?: number;
  liq_24h_long_usd?: number;
  liq_24h_short_usd?: number;
  liq_24h_total_usd?: number;
  liq_24h_events?: number;
  liq_1h_pressure?: string;
  liq_4h_pressure?: string;
  liq_24h_pressure?: string;
}

export interface MarketBriefTldr {
  now: string;
  short_read: string;
  however: string;
}

export interface MarketBrief {
  headline: string;
  market_status: string;
  stance: "prefer_long" | "prefer_short" | "wait";
  suggestions: string[];
  risks: string[];
  evidence_refs: string[];
  tldr?: MarketBriefTldr | null;
  asset?: string | null;
  stale?: boolean;
  tab_assets?: string[];
  as_of: string;
  provider: string;
  source: string;
  snapshot_hash?: string;
  pulse?: PulseSnapshot | null;
}
