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
          <DataTableHeaderCell>Price</DataTableHeaderCell>
          <DataTableHeaderCell>Leverage</DataTableHeaderCell>
          <DataTableHeaderCell>Win Rate</DataTableHeaderCell>
          <DataTableHeaderCell>Strategy</DataTableHeaderCell>
          <DataTableHeaderCell>Confidence</DataTableHeaderCell>
          <DataTableHeaderCell>Time</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {alerts.map((alert) => {
            const price = alert.entry_price ?? alert.exit_price;
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
                      {alert.trader_address}
                    </span>
                  </Link>
                </DataTableCell>
                <DataTableCell>
                  <AssetIcon asset={alert.asset} />
                </DataTableCell>
                <DataTableCell>
                  <Badge variant={alert.alert_type}>
                    {alert.alert_type.toUpperCase()}
                  </Badge>
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
                  {price ? formatPrice(price, alert.asset) : "—"}
                </DataTableCell>
                <DataTableCell>{alert.leverage}x</DataTableCell>
                <DataTableCell>
                  <span className="text-positive font-medium">
                    {alert.win_rate}%
                  </span>
                </DataTableCell>
                <DataTableCell className="text-text-muted">
                  {alert.inferred_strategy}
                </DataTableCell>
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
    </DashboardLayout>
  );
}
