import Link from "next/link";
import type { PaperPortfolioSummary } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { formatPct, formatTimeAgo, formatUsd } from "@/lib/api";

export function PaperPortfolioCard({
  summary,
  compact = false,
}: {
  summary: PaperPortfolioSummary;
  compact?: boolean;
}) {
  const positive = summary.return_pct >= 0;
  return (
    <div className="rounded-xl border border-border bg-bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[10px] uppercase tracking-wide text-text-dim">
              Paper Portfolio · experimental strategy
            </p>
            <Badge variant={summary.warming_up ? "hold" : "accent"}>
              {summary.warming_up ? "WARMING UP" : summary.status.toUpperCase()}
            </Badge>
          </div>
          <p className="mt-2 text-2xl font-semibold text-text-primary">
            {formatUsd(summary.initial_cash)} → {formatUsd(summary.nav)}
          </p>
          <p className={`mt-1 text-sm ${positive ? "text-positive" : "text-negative"}`}>
            {formatPct(summary.return_pct)} net
          </p>
        </div>
        <Link href="/performance" className="text-xs text-accent hover:underline">
          Full performance
        </Link>
      </div>

      <div className={`mt-4 grid ${compact ? "grid-cols-3" : "grid-cols-2 sm:grid-cols-4"} gap-3`}>
        <Metric
          label="BTC hold"
          value={
            summary.benchmark_return_pct == null
              ? "Warming up"
              : formatPct(summary.benchmark_return_pct)
          }
        />
        <Metric label="Max drawdown" value={formatPct(summary.max_drawdown_pct)} />
        <Metric label="Simulated fills" value={String(summary.trades_count)} />
        {!compact && (
          <Metric
            label="Exposure"
            value={`${summary.current_positions.length} positions · ${formatUsd(summary.gross_exposure_usd)}`}
          />
        )}
      </div>

      <p className="mt-4 text-xs text-text-muted">
        Recorded sample: {summary.observed_hour_buckets ?? 0}/720 hourly evaluations
        {" · "}{summary.fully_closed_positions_count ?? 0}/100 full closes.
        {summary.minimum_sample_met
          ? " Minimum counts reached; source and accounting review still required."
          : " Still below the minimum validation sample."}
      </p>
      {summary.evaluation_paused !== false && (
        <p className="mt-2 text-xs text-negative">
          Evaluation paused while source data is unverified or incomplete.
          Showing the last recorded results.
        </p>
      )}

      <p className="mt-4 text-[11px] leading-relaxed text-text-dim">
        Top 5 Whale + recent Top 5 flow, confirmed by 1h/4h trend · fees,
        slippage and funding included · updated {formatTimeAgo(summary.updated_at)}
      </p>
      <p className="mt-2 text-[11px] leading-relaxed text-text-dim">
        Simulated trades with {formatUsd(summary.initial_cash)} virtual capital.
        Losses are possible. Past paper results do not predict future returns.
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-text-dim">{label}</p>
      <p className="mt-1 text-sm font-medium text-text-primary">{value}</p>
    </div>
  );
}
