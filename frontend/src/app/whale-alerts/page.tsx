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
import {
  getWhaleAlerts,
  formatUsd,
  formatPrice,
  formatTimeAgo,
} from "@/lib/api";

const STALE_MS = 45 * 60 * 1000;

function isStale(timestamp: string): boolean {
  const t = Date.parse(timestamp);
  if (Number.isNaN(t)) return false;
  return Date.now() - t > STALE_MS;
}

export default async function WhaleAlertsPage() {
  const alerts = await getWhaleAlerts();

  return (
    <DashboardLayout>
      <PageHeader
        title="Whale Alerts"
        description="Position entry and exit detection for top Hyperliquid traders"
      />

      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>Trader</DataTableHeaderCell>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Type</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>Size</DataTableHeaderCell>
          <DataTableHeaderCell>Entry / Mark</DataTableHeaderCell>
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
                      {alert.alert_type.toUpperCase()}
                    </Badge>
                    {stale && <Badge variant="exit">STALE</Badge>}
                  </div>
                </DataTableCell>
                <DataTableCell>
                  <Badge variant={alert.side}>
                    {alert.side.toUpperCase()}
                  </Badge>
                </DataTableCell>
                <DataTableCell className="font-medium">
                  {formatUsd(alert.size_usd)}
                </DataTableCell>
                <DataTableCell>
                  <div className="flex flex-col text-xs text-text-muted">
                    <span>
                      E{" "}
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

      <p className="text-xs text-text-dim mt-4">
        Entry/Mark and uPnL/ROI come from clearinghouse + mark ticks. STALE means
        the event is older than 45 minutes. Book % is tracked-whale long share for
        that asset.
      </p>
    </DashboardLayout>
  );
}
