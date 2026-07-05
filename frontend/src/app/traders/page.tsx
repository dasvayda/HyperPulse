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
  TrendValue,
} from "@/components/ui/DataTable";
import { SparkBarBackground } from "@/components/ui/SparkBar";
import { getTraders, getPipelineStatus, formatUsd } from "@/lib/api";

export default async function TradersPage() {
  const [traders, pipeline] = await Promise.all([
    getTraders(),
    getPipelineStatus(),
  ]);

  return (
    <DashboardLayout>
      <PageHeader
        title="Traders"
        description="Top traders from the Hyperliquid leaderboard"
        actions={
          <span className="text-xs text-text-dim border border-border rounded-full px-3 py-1">
            Data source: {pipeline.data_source}
          </span>
        }
      />

      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>#</DataTableHeaderCell>
          <DataTableHeaderCell>Trader</DataTableHeaderCell>
          <DataTableHeaderCell>Account Value</DataTableHeaderCell>
          <DataTableHeaderCell>All-time PnL</DataTableHeaderCell>
          <DataTableHeaderCell>Volume</DataTableHeaderCell>
          <DataTableHeaderCell>Risk</DataTableHeaderCell>
          <DataTableHeaderCell>PnL Curve</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {traders.map((trader) => (
            <DataTableRow key={trader.address}>
              <DataTableCell className="text-text-muted font-mono">
                {trader.rank}
              </DataTableCell>
              <DataTableCell>
                <Link
                  href={`/traders/${encodeURIComponent(trader.address)}`}
                  className="flex flex-col"
                >
                  <span className="text-accent hover:underline font-medium">
                    {trader.alias}
                  </span>
                  <span className="text-xs text-text-dim font-mono">
                    {trader.address}
                  </span>
                </Link>
              </DataTableCell>
              <DataTableCell className="font-medium">
                {formatUsd(trader.account_value_usd)}
              </DataTableCell>
              <DataTableCell>
                <TrendValue
                  value={formatUsd(trader.pnl_usd)}
                  pct={trader.pnl_change_pct}
                />
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {trader.volume_usd > 0 ? formatUsd(trader.volume_usd) : "—"}
              </DataTableCell>
              <DataTableCell>
                <div className="flex items-center gap-2">
                  <div className="w-10 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        trader.risk_score > 70
                          ? "bg-negative"
                          : trader.risk_score > 50
                            ? "bg-accent"
                            : "bg-positive"
                      }`}
                      style={{ width: `${trader.risk_score}%` }}
                    />
                  </div>
                  <span className="text-xs text-text-muted">
                    {trader.risk_score}
                  </span>
                </div>
              </DataTableCell>
              <DataTableCell>
                <SparkBarBackground
                  values={trader.sparkline}
                  color={trader.pnl_change_pct >= 0 ? "positive" : "negative"}
                >
                  <span className="text-xs text-text-dim">day → all-time</span>
                </SparkBarBackground>
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <p className="text-xs text-text-dim mt-4">
        Live leaderboard fields: account value, all-time PnL/ROI, trading volume,
        window PnL curve, and ROI volatility risk. Win rate, hold time, assets, and
        strategy require fill-level analytics and are shown on detail pages when available.
      </p>
    </DashboardLayout>
  );
}
