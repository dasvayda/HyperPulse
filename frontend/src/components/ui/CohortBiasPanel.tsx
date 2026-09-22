import type { CohortBiasResponse } from "@/types";
import { formatUsd } from "@/lib/api";

interface CohortBiasPanelProps {
  data: CohortBiasResponse;
  className?: string;
}

export function CohortBiasPanel({ data, className = "" }: CohortBiasPanelProps) {
  const rows = data.assets.slice(0, 5);

  return (
    <div
      className={`rounded-xl border border-border bg-bg-surface p-5 flex flex-col gap-3 w-full ${className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-text-primary">
          Smart vs Rest
        </h3>
        <span className="text-[10px] uppercase tracking-wide text-text-dim">
          Top {data.smart_n} by size
        </span>
      </div>
      <p className="text-xs text-text-dim">
        Long % by $ — Smart Money cohort vs the rest of tracked whales
      </p>

      {rows.length === 0 ? (
        <p className="text-sm text-text-muted">Whale book still warming up.</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => {
            const smart = row.smart_long_pct;
            const rest = row.rest_long_pct;
            const delta = row.delta_pp;
            const deltaClass =
              delta == null
                ? "text-text-dim"
                : delta >= 8
                  ? "text-positive"
                  : delta <= -8
                    ? "text-negative"
                    : "text-text-muted";
            return (
              <li
                key={row.asset}
                className="grid grid-cols-[2.75rem_3.25rem_minmax(0,1fr)_minmax(0,1fr)] gap-x-2 items-center"
              >
                <span className="text-xs font-medium text-text-primary truncate">
                  {row.asset}
                </span>
                <span
                  className={`text-[11px] tabular-nums text-right ${deltaClass}`}
                >
                  {delta == null
                    ? "—"
                    : `${delta >= 0 ? "+" : ""}${delta.toFixed(0)} pp`}
                </span>
                <div className="min-w-0 text-[11px] text-text-muted">
                  <span className="text-text-dim">Smart </span>
                  {smart != null ? `${smart.toFixed(0)}% long` : "—"}
                  <span className="block text-text-dim">
                    {formatUsd(row.smart_notional_usd)} · {row.smart_whales}w
                  </span>
                </div>
                <div className="min-w-0 text-[11px] text-text-muted">
                  <span className="text-text-dim">Rest </span>
                  {rest != null ? `${rest.toFixed(0)}% long` : "—"}
                  <span className="block text-text-dim">
                    {formatUsd(row.rest_notional_usd)} · {row.rest_whales}w
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
