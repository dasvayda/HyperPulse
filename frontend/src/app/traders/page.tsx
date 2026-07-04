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
import { Badge } from "@/components/ui/Badge";
import { SparkBarBackground } from "@/components/ui/SparkBar";
import { getTraders, formatUsd, formatPct } from "@/lib/api";

export default async function TradersPage() {
  const traders = await getTraders();

  return (
    <DashboardLayout>
      <PageHeader
        title="Traders"
        description="Top profitable traders on Hyperliquid ranked by performance"
      />

      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>#</DataTableHeaderCell>
          <DataTableHeaderCell>Trader</DataTableHeaderCell>
          <DataTableHeaderCell>PnL</DataTableHeaderCell>
          <DataTableHeaderCell>Win Rate</DataTableHeaderCell>
          <DataTableHeaderCell>Avg Hold</DataTableHeaderCell>
          <DataTableHeaderCell>Trades</DataTableHeaderCell>
          <DataTableHeaderCell>Assets</DataTableHeaderCell>
          <DataTableHeaderCell>Strategy</DataTableHeaderCell>
          <DataTableHeaderCell>Risk</DataTableHeaderCell>
          <DataTableHeaderCell>Trend</DataTableHeaderCell>
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
              <DataTableCell>
                <SparkBarBackground
                  values={trader.sparkline}
                  color={trader.pnl_change_pct >= 0 ? "positive" : "negative"}
                >
                  <TrendValue
                    value={formatUsd(trader.pnl_usd)}
                    pct={trader.pnl_change_pct}
                  />
                </SparkBarBackground>
              </DataTableCell>
              <DataTableCell>
                <span className="text-positive font-medium">
                  {trader.win_rate}%
                </span>
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {trader.avg_hold_hours}h
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {trader.total_trades.toLocaleString()}
              </DataTableCell>
              <DataTableCell>
                <div className="flex gap-1">
                  {trader.preferred_assets.map((a) => (
                    <Badge key={a} variant="default">
                      {a}
                    </Badge>
                  ))}
                </div>
              </DataTableCell>
              <DataTableCell>
                <div className="flex gap-1 flex-wrap">
                  {trader.strategy_tags.map((tag) => (
                    <Badge key={tag} variant="accent">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </DataTableCell>
              <DataTableCell>
                <div className="flex items-center gap-2">
                  <div className="w-10 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                    <div
                      className={`h-full rounded-full ${trader.risk_score > 70 ? "bg-negative" : trader.risk_score > 50 ? "bg-accent" : "bg-positive"}`}
                      style={{ width: `${trader.risk_score}%` }}
                    />
                  </div>
                  <span className="text-xs text-text-muted">
                    {trader.risk_score}
                  </span>
                </div>
              </DataTableCell>
              <DataTableCell>
                <span
                  className={
                    trader.pnl_change_pct >= 0
                      ? "text-positive text-xs font-medium"
                      : "text-negative text-xs font-medium"
                  }
                >
                  {formatPct(trader.pnl_change_pct)}
                </span>
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>
    </DashboardLayout>
  );
}
