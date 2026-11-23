export interface LiquidationWindow {
  status: "ok" | "partial" | "unavailable";
  gap: boolean;
  long_usd: number | null;
  short_usd: number | null;
  observed_long_usd: number;
  observed_short_usd: number;
  events: number;
}

export interface WatchedLiquidations {
  scope: "watched_wallets";
  source: string;
  wallets: string[];
  as_of: string;
  windows: Record<"1h" | "4h" | "24h", LiquidationWindow>;
  recent_events: {
    id: string; wallet: string; asset: string; side: "long" | "short";
    size_usd: number; price: number; event_at: string; tx_hash: string;
  }[];
}

export function sampleAmounts(window?: LiquidationWindow) {
  const complete = window?.status === "ok" && !window.gap
    && window.long_usd != null && window.short_usd != null;
  return {
    available: complete || window?.status === "partial",
    complete,
    long: complete ? window.long_usd! : window?.observed_long_usd ?? 0,
    short: complete ? window.short_usd! : window?.observed_short_usd ?? 0,
  };
}
