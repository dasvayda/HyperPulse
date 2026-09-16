import type { CohortBiasAsset, CohortBiasResponse } from "@/types";
import { formatUsd } from "@/lib/api";

interface CohortHeatmapProps {
  data: CohortBiasResponse;
  className?: string;
}

/** Long-share color ramp: green = long-heavy, red = short-heavy, grey = balanced. */
function cellClass(pct: number | null | undefined): string {
  if (pct == null) return "bg-bg-elevated text-text-dim";
  if (pct >= 70) return "bg-positive/25 text-positive";
  if (pct >= 58) return "bg-positive/15 text-positive";
  if (pct <= 30) return "bg-negative/25 text-negative";
  if (pct <= 42) return "bg-negative/15 text-negative";
  return "bg-bg-elevated text-text-primary";
}

function cellText(pct: number | null | undefined): string {
  return pct == null ? "—" : `${pct.toFixed(0)}%`;
}

function Cell({ pct }: { pct: number | null | undefined }) {
  return (
    <div
      className={`rounded-md px-2 py-2 text-center text-xs font-medium ${cellClass(pct)}`}
    >
      {cellText(pct)}
    </div>
  );
}

function Row({ row }: { row: CohortBiasAsset }) {
  return (
    <div className="grid grid-cols-[minmax(72px,1.2fr)_repeat(3,minmax(44px,1fr))] gap-1.5 items-center">
      <div className="min-w-0">
        <p className="text-xs font-medium text-text-primary truncate">
          {row.asset}
          {row.thin && (
            <span className="ml-1.5 text-[9px] uppercase tracking-wide text-text-dim">
              thin
            </span>
          )}
        </p>
        <p className="text-[10px] text-text-dim truncate">
          {row.whale_oi_pct != null
            ? `${row.whale_oi_pct.toFixed(1)}% of OI`
            : formatUsd(row.smart_notional_usd + row.rest_notional_usd)}
        </p>
      </div>
      <Cell pct={row.smart_long_pct} />
      <Cell pct={row.rest_long_pct} />
      <Cell pct={row.all_long_pct} />
    </div>
  );
}

export function CohortHeatmap({ data, className = "" }: CohortHeatmapProps) {
  const rows = data.assets.slice(0, 8);

  return (
    <div
      className={`rounded-xl border border-border bg-bg-surface p-5 ${className}`}
    >
      <div className="flex items-center justify-between gap-3 mb-1">
        <h3 className="text-sm font-semibold text-text-primary">
          Cohort heatmap
        </h3>
        <span className="text-[10px] uppercase tracking-wide text-text-dim">
          Top {data.smart_n} smart
        </span>
      </div>
      <p className="text-xs text-text-dim mb-4">
        Long share by $ — green long-heavy, red short-heavy, grey balanced.
        &quot;Thin&quot; names sit outside the volume majors, so whale size moves
        them more.
      </p>

      {rows.length === 0 ? (
        <p className="text-sm text-text-muted">Whale book still warming up.</p>
      ) : (
        <div className="space-y-1.5">
          <div className="grid grid-cols-[minmax(72px,1.2fr)_repeat(3,minmax(44px,1fr))] gap-1.5">
            <span className="text-[10px] uppercase tracking-wide text-text-dim">
              Coin
            </span>
            <span className="text-[10px] uppercase tracking-wide text-text-dim text-center">
              Smart
            </span>
            <span className="text-[10px] uppercase tracking-wide text-text-dim text-center">
              Rest
            </span>
            <span className="text-[10px] uppercase tracking-wide text-text-dim text-center">
              All
            </span>
          </div>
          {rows.map((row) => (
            <Row key={row.asset} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}
