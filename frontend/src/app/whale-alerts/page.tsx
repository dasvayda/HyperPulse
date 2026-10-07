import Link from "next/link";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeaderCell,
  DataTableRow,
  PageHeader,
  AssetIcon,
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import {
  getWhaleAlerts,
  formatUsd,
  formatPrice,
  formatTimeAgo,
  getExplorerTxUrl,
} from "@/lib/api";

const STALE_MS = 45 * 60 * 1000;

function isStale(timestamp: string): boolean {
  const t = Date.parse(timestamp);
  if (Number.isNaN(t)) return false;
  return Date.now() - t > STALE_MS;
}

type WhaleAlertsPageProps = {
  searchParams: Promise<{ fresh?: string }>;
};

export default async function WhaleAlertsPage({
  searchParams,
}: WhaleAlertsPageProps) {
  const params = await searchParams;
  const freshOnly = params.fresh === "true" || params.fresh === "1";
  const alerts = await getWhaleAlerts({ fresh: freshOnly });

  const chipClass = (active: boolean) =>
    `text-xs rounded-full border px-3 py-1.5 transition-colors ${
      active
        ? "border-accent text-accent bg-accent/10"
        : "border-border text-text-muted hover:border-accent/40 hover:text-text-primary"
    }`;

  return (
    <DashboardLayout>
      <PageHeader
        title="Whale Alerts"
        description="Tracked position changes. Verified fills are linked when they match the snapshot change."
      />

      <div className="flex flex-wrap gap-2 mb-4">
        <Link href="/whale-alerts" className={chipClass(!freshOnly)}>
          All
        </Link>
        <Link href="/whale-alerts?fresh=true" className={chipClass(freshOnly)}>
          Fresh 24h
        </Link>
      </div>

      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>Trader</DataTableHeaderCell>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Type</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Position / change">
              Total position comes from the latest Hyperliquid account snapshot.
              Change compares this snapshot with the prior tracked snapshot.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Avg entry / mark">
              Avg entry is for the whole open position. Mark is the latest market
              price. Neither is the price of the latest fill unless a Verified
              fill line says so.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>uPnL / ROI</DataTableHeaderCell>
          <DataTableHeaderCell>Leverage</DataTableHeaderCell>
          <DataTableHeaderCell>Book</DataTableHeaderCell>
          <DataTableHeaderCell>Strategy</DataTableHeaderCell>
          <DataTableHeaderCell>Confidence</DataTableHeaderCell>
          <DataTableHeaderCell>Time</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {alerts.map((alert) => {
            const stale = isStale(alert.timestamp);
            const isFreshEntry =
              alert.alert_type === "entry" &&
              !Number.isNaN(Date.parse(alert.timestamp)) &&
              Date.now() - Date.parse(alert.timestamp) < 24 * 60 * 60 * 1000;
            const strategy =
              alert.inferred_strategy &&
              alert.inferred_strategy.toLowerCase() !== "unknown"
                ? alert.inferred_strategy
                : "—";
            return (
              <DataTableRow key={alert.id}>
                <DataTableCell>
                  <Link
                    href={`/traders/${encodeURIComponent(alert.trader_address)}`}
                    className="flex flex-col"
                  >
                    <span className="text-accent hover:underline font-medium">
                      {alert.trader_alias}
                    </span>
                    <span className="text-xs text-text-dim font-mono">
                      {alert.trader_address.slice(0, 10)}…
                    </span>
                  </Link>
                </DataTableCell>
                <DataTableCell>
                  <AssetIcon asset={alert.asset} />
                </DataTableCell>
                <DataTableCell>
                  <div className="flex flex-col gap-1">
                    <Badge variant={alert.alert_type}>
                      {alert.alert_type === "entry" ? "POSITION UP" : "POSITION DOWN"}
                    </Badge>
                    {isFreshEntry && <Badge variant="entry">LAST 24H</Badge>}
                    {stale && <Badge variant="exit">STALE</Badge>}
                  </div>
                </DataTableCell>
                <DataTableCell>
                  <Badge variant={alert.side}>
                    {alert.side.toUpperCase()}
                  </Badge>
                </DataTableCell>
                <DataTableCell className="font-medium">
                  <div className="flex flex-col gap-1">
                    <span>Position {formatUsd(alert.size_usd)}</span>
                    {alert.size_delta_usd != null &&
                    alert.size_delta_usd !== 0 ? (
                      <span className="text-xs text-text-muted">
                        {alert.execution?.verified ? "Verified fill" : "Snapshot change"} {formatUsd(alert.size_delta_usd)}
                      </span>
                    ) : null}
                    {alert.execution?.verified ? (
                      <div className="text-xs text-positive">
                        <span>
                          {alert.execution.fill_count} fills @{" "}
                          {alert.execution.price_low != null
                            ? formatPrice(alert.execution.price_low, alert.asset)
                            : "—"}
                          {alert.execution.price_high != null &&
                          alert.execution.price_high !== alert.execution.price_low
                            ? `–${formatPrice(alert.execution.price_high, alert.asset)}`
                            : ""}
                        </span>
                        {alert.execution.tx_hashes.length > 0 ? (
                          <span className="ml-2">
                            {alert.execution.tx_hashes.slice(0, 3).map((hash, index) => (
                              <a
                                key={hash}
                                href={getExplorerTxUrl(hash)}
                                target="_blank"
                                rel="noreferrer"
                                className="text-accent hover:underline mr-1"
                              >
                                Tx {index + 1}
                              </a>
                            ))}
                          </span>
                        ) : null}
                      </div>
                    ) : alert.size_delta_usd != null ? (
                      <span className="text-xs text-text-dim">Fills not verified</span>
                    ) : null}
                  </div>
                </DataTableCell>
                <DataTableCell>
                  <div className="flex flex-col text-xs text-text-muted">
                    <span>
                      Avg E{" "}
                      {alert.entry_price != null
                        ? formatPrice(alert.entry_price, alert.asset)
                        : "—"}
                    </span>
                    <span>
                      M{" "}
                      {alert.mark_price != null
                        ? formatPrice(alert.mark_price, alert.asset)
                        : "—"}
                    </span>
                  </div>
                </DataTableCell>
                <DataTableCell>
                  {alert.unrealized_pnl_usd != null || alert.roi_pct != null ? (
                    <div className="flex flex-col text-xs">
                      {alert.unrealized_pnl_usd != null && (
                        <span
                          className={
                            alert.unrealized_pnl_usd >= 0
                              ? "text-positive font-medium"
                              : "text-negative font-medium"
                          }
                        >
                          {formatUsd(alert.unrealized_pnl_usd)}
                        </span>
                      )}
                      {alert.roi_pct != null && (
                        <span
                          className={
                            alert.roi_pct >= 0
                              ? "text-positive"
                              : "text-negative"
                          }
                        >
                          {alert.roi_pct >= 0 ? "+" : ""}
                          {alert.roi_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-text-dim">—</span>
                  )}
                </DataTableCell>
                <DataTableCell>{alert.leverage}x</DataTableCell>
                <DataTableCell className="text-xs text-text-muted">
                  {alert.whale_long_pct != null
                    ? `${alert.whale_long_pct.toFixed(0)}% L`
                    : "—"}
                </DataTableCell>
                <DataTableCell className="text-text-muted">{strategy}</DataTableCell>
                <DataTableCell>
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                      <div
                        className="h-full rounded-full bg-accent"
                        style={{ width: `${alert.confidence_score}%` }}
                      />
                    </div>
                    <span className="text-xs text-text-muted">
                      {alert.confidence_score}%
                    </span>
                  </div>
                </DataTableCell>
                <DataTableCell className="text-text-muted">
                  {formatTimeAgo(alert.timestamp)}
                </DataTableCell>
              </DataTableRow>
            );
          })}
        </DataTableBody>
      </DataTable>

      <details className="mt-4 rounded-xl border border-border bg-bg-surface px-4 py-3 text-xs text-text-muted">
        <summary className="cursor-pointer font-medium text-text-primary">
          How each whale alert is sourced
        </summary>
        <div className="mt-3 space-y-2 leading-relaxed">
          <p>
            <span className="font-medium text-text-primary">Why it appeared:</span>{" "}
            POSITION UP or DOWN is the change between two tracked Hyperliquid
            account snapshots. It is not automatically a single trade.
          </p>
          <p>
            <span className="font-medium text-text-primary">Verified fill:</span>{" "}
            HyperCore fills are checked only inside that same snapshot window.
            A matching fill gets its real price and explorer links; otherwise we
            show “Snapshot change” and no fill price.
          </p>
          <p>
            <span className="font-medium text-text-primary">Position numbers:</span>{" "}
            size, average entry, leverage, and unrealized PnL come from
            Hyperliquid&apos;s account state. Mark comes from the latest market
            snapshot. Avg E is the accumulated position average, not the latest
            fill price.
          </p>
          <p>
            <span className="font-medium text-text-primary">Confidence:</span>{" "}
            a rule-based alert-quality score, not a forecast of profit. STALE
            means the alert is older than 45 minutes.
          </p>
        </div>
      </details>
    </DashboardLayout>
  );
}
