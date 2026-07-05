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
  entry_price: number | null;
  exit_price: number | null;
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

export interface TraderDetail extends TraderProfile {
  recent_positions: {
    asset: string;
    side: string;
    type: string;
    size_usd: number;
    price: number | null;
    timestamp: string;
  }[];
  behavior_summary: string;
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

export interface DashboardStats {
  active_whales: number;
  alerts_24h: number;
  total_liquidations_24h: number;
  top_asset: string;
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
  win_rate: number;
  pnl_change_pct: number;
  strategy_tags: string[];
  risk_score: number;
  momentum_score: number;
  consistency_score: number;
  sparkline: number[];
}

export interface MarketInsight {
  id: string;
  title: string;
  summary: string;
  asset: string | null;
  confidence: number;
  signals: string[];
  created_at: string;
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
}
