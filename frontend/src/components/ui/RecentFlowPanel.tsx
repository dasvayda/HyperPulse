import type { TraderFillsSummary } from "@/types";
import { formatUsd, formatTimeAgo } from "@/lib/api";

interface RecentFlowPanelProps {
  fills: TraderFillsSummary;
  className?: string;
}

export function RecentFlowPanel({ fills, className = "" }: RecentFlowPanelProps) {
  const netPositive = fills.net_usd >= 0;

  return (
    <div
      className={`rounded-xl border border-border bg-bg-surface p-5 ${className}`}
    >
      <div className="flex items-center justify-between gap-3 mb-1">
        <h3 className="text-sm font-semibold text-text-primary">
          Last {fills.window_hours}h flow
        </h3>
        <span className="text-[10px] uppercase tracking-wide text-text-dim">
          {fills.fills} fills
          {fills.last_fill_at ? ` · ${formatTimeAgo(fills.last_fill_at)}` : ""}
        </span>
      </div>
      <p className="text-xs text-text-dim mb-4">
        Executed buys vs sells on Hyperliquid (userFills), not open notional
      </p>

      {fills.fills === 0 ? (
        <p className="text-sm text-text-muted">
          No fills in the last {fills.window_hours}h — position is being held, not traded.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-text-dim mb-1">
                Bought
              </p>
              <p className="text-sm font-medium text-positive">
                {formatUsd(fills.buy_usd)}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wide text-text-dim mb-1">
                Sold
              </p>
              <p className="text-sm font-medium text-negative">
                {formatUsd(fills.sell_usd)}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wide text-text-dim mb-1">
                Net
              </p>
              <p
                className={`text-sm font-medium ${
                  netPositive ? "text-positive" : "text-negative"
                }`}
              >
                {formatUsd(fills.net_usd)}
              </p>
            </div>
          </div>

          <ul className="space-y-2 mb-3">
            {fills.assets.map((row) => {
              const total = row.buy_usd + row.sell_usd;
              const buyShare = total > 0 ? (row.buy_usd / total) * 100 : 0;
              return (
                <li key={row.asset} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-text-primary">
                      {row.asset}
                    </span>
                    <span
                      className={
                        row.net_usd >= 0 ? "text-positive" : "text-negative"
                      }
                    >
                      {formatUsd(row.net_usd)} net
                    </span>
                  </div>
                  <div className="h-1.5 w-full rounded-full overflow-hidden bg-bg-elevated flex">
                    <div
                      className="h-full bg-positive"
                      style={{ width: `${buyShare}%` }}
                    />
                    <div
                      className="h-full bg-negative"
                      style={{ width: `${100 - buyShare}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>

          {fills.position_check && (
            <p className="text-xs text-text-muted border-t border-border pt-3">
              {fills.position_check}
            </p>
          )}
        </>
      )}
    </div>
  );
}
