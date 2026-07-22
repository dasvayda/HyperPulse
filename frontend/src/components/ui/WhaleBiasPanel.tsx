"use client";

import { useState } from "react";
import type { WhaleBookSummary } from "@/types";
import { formatUsd } from "@/lib/api";

interface WhaleBiasPanelProps {
  summary: WhaleBookSummary;
  className?: string;
}

type Mode = "count" | "value";

export function WhaleBiasPanel({ summary, className = "" }: WhaleBiasPanelProps) {
  const [mode, setMode] = useState<Mode>("value");

  const hasPositions = summary.with_positions > 0;
  const longPct = mode === "value" ? summary.long_pct : summary.whale_count_long_pct;
  const shortPct = hasPositions ? Math.max(0, 100 - longPct) : 0;

  return (
    <div
      className={`rounded-xl border border-border bg-bg-surface p-5 flex flex-col gap-4 w-full ${className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-text-primary">
          Whale Long / Short
        </h3>
        <div className="flex rounded-full border border-border overflow-hidden text-xs shrink-0">
          <button
            type="button"
            onClick={() => setMode("count")}
            className={`px-2.5 py-1 transition-colors ${
              mode === "count"
                ? "bg-accent text-bg-primary font-medium"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Whales
          </button>
          <button
            type="button"
            onClick={() => setMode("value")}
            className={`px-2.5 py-1 transition-colors ${
              mode === "value"
                ? "bg-accent text-bg-primary font-medium"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Value
          </button>
        </div>
      </div>

      {hasPositions ? (
        <>
          <div className="flex items-center justify-between text-xs font-medium">
            <span className="text-positive">
              Long {longPct.toFixed(0)}%
              {mode === "value" ? " by $" : " of whales"}
            </span>
            <span className="text-negative">
              Short {shortPct.toFixed(0)}%
              {mode === "value" ? " by $" : " of whales"}
            </span>
          </div>
          <div className="h-3 w-full rounded-full overflow-hidden bg-bg-elevated flex">
            <div
              className="h-full bg-positive transition-all"
              style={{ width: `${longPct}%` }}
            />
            <div
              className="h-full bg-negative transition-all"
              style={{ width: `${shortPct}%` }}
            />
          </div>
          <p className="text-sm text-text-muted">
            {mode === "value"
              ? `${formatUsd(summary.long_notional_usd)} long vs ${formatUsd(
                  summary.short_notional_usd,
                )} short (notional)`
              : `${summary.long_whale_count} whales net-long vs ${summary.short_whale_count} net-short`}
          </p>
          <p className="text-xs text-text-dim">
            {summary.with_positions}/{summary.tracked} tracked whales positioned
          </p>
        </>
      ) : (
        <p className="text-sm text-text-muted">
          No open whale positions tracked yet.
        </p>
      )}
    </div>
  );
}
