import type {
  AlertHistoryItem,
  CoinPulse,
  BiggestPosition,
  CohortBiasResponse,
  DashboardStats,
  LiqProximityRow,
  LiquidationEvent,
  LiquidationZone,
  MarketBrief,
  MarketInsight,
  MarketPulse,
  MarketStatus,
  PipelineStatus,
  SmartMoneyRank,
  StrategyInference,
  TraderDetail,
  TraderProfile,
  WhaleAlert,
  WhaleBookSummary,
  PerformanceRankingResponse,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function fetchApi<T>(
  path: string,
  init?: RequestInit & { next?: { revalidate?: number | false } },
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    next: { revalidate: 30 },
    ...init,
  });
  if (!res.ok) {
    throw new ApiError(res.status, `API error: ${res.status}`);
  }
  return res.json();
}

export function getDashboardStats(): Promise<DashboardStats> {
  return fetchApi("/api/v1/dashboard/stats");
}

export function getWhaleAlerts(params?: {
  asset?: string;
  alert_type?: string;
  fresh?: boolean;
}): Promise<WhaleAlert[]> {
  const search = new URLSearchParams();
  if (params?.asset) search.set("asset", params.asset);
  if (params?.alert_type) search.set("alert_type", params.alert_type);
  if (params?.fresh) search.set("fresh", "true");
  const qs = search.toString();
  return fetchApi(`/api/v1/whale-alerts${qs ? `?${qs}` : ""}`);
}

export function getTraders(): Promise<TraderProfile[]> {
  return fetchApi("/api/v1/traders");
}

export function getTrader(address: string): Promise<TraderDetail> {
  return fetchApi(`/api/v1/traders/${encodeURIComponent(address)}`, {
    cache: "no-store",
  });
}

export function getLiquidationZones(asset?: string): Promise<LiquidationZone[]> {
  const qs = asset ? `?asset=${asset}` : "";
  return fetchApi(`/api/v1/liquidations/zones${qs}`);
}

export function getLiquidationEvents(asset?: string): Promise<LiquidationEvent[]> {
  const qs = asset ? `?asset=${asset}` : "";
  return fetchApi(`/api/v1/liquidations/events${qs}`);
}

export function getRankings(): Promise<SmartMoneyRank[]> {
  return fetchApi("/api/v2/rankings");
}

export function getPerformanceRankings(): Promise<PerformanceRankingResponse> {
  return fetchApi("/api/v2/performance");
}

export function getAIInsights(): Promise<MarketInsight[]> {
  return fetchApi("/api/v2/insights");
}

export function getMarketBrief(asset?: string): Promise<MarketBrief> {
  const qs = asset ? `?asset=${encodeURIComponent(asset)}` : "";
  return fetchApi(`/api/v2/insights/brief${qs}`);
}

export function getInferences(): Promise<StrategyInference[]> {
  return fetchApi("/api/v2/inferences");
}

export function getAlertsHistory(status?: string): Promise<AlertHistoryItem[]> {
  const qs = status ? `?status=${status}` : "";
  return fetchApi(`/api/v2/alerts${qs}`);
}

export function getPipelineStatus(): Promise<PipelineStatus> {
  return fetchApi("/api/v2/pipeline/status");
}

export function getMarketStatus(): Promise<MarketStatus> {
  return fetchApi("/api/v2/market/status");
}

export function getWhaleBookSummary(): Promise<WhaleBookSummary> {
  return fetchApi("/api/v2/whale-book/summary");
}

export function getCoinPulse(assets: string[] = []): Promise<CoinPulse[]> {
  const qs = assets.length ? `?assets=${assets.map(encodeURIComponent).join("&assets=")}` : "";
  return fetchApi(`/api/v2/market/coin-pulse${qs}`);
}

export function getBiggestPositions(limit = 8): Promise<BiggestPosition[]> {
  return fetchApi(`/api/v2/whale-book/biggest-positions?limit=${limit}`);
}

export function getCohortBias(assets: string[] = []): Promise<CohortBiasResponse> {
  const qs = assets.length
    ? `?assets=${assets.map(encodeURIComponent).join("&assets=")}`
    : "";
  return fetchApi(`/api/v2/whale-book/cohort-bias${qs}`);
}

export function getLiqProximity(limit = 10): Promise<LiqProximityRow[]> {
  return fetchApi(`/api/v2/whale-book/liq-proximity?limit=${limit}`);
}

export function getMarketPulse(topN = 20): Promise<MarketPulse> {
  return fetchApi(`/api/v2/market/pulse?top_n=${topN}`);
}

export function formatConfidence(value: number): string {
  return `${value.toFixed(0)}%`;
}

/** Composite scores on a fixed 0–100 scale (e.g. Smart Money Score). */
export function formatScore100(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  return `${text} / 100`;
}

export function formatUsd(value: number): string {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}$${abs.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function formatPrice(value: number, asset: string): string {
  if (asset === "BTC") return `$${value.toLocaleString()}`;
  if (value >= 1000) return `$${value.toLocaleString()}`;
  return `$${value.toFixed(2)}`;
}

export function formatPct(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

/** Funding is usually a tiny decimal rate; show more precision. */
export function formatFundingPct(rate: number): string {
  const pct = rate * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(4)}%`;
}

export function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function getExplorerTxUrl(hash: string): string {
  return `https://app.hyperliquid.xyz/explorer/tx/${encodeURIComponent(hash)}`;
}
