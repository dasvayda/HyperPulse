import Link from "next/link";
import { notFound } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeaderCell,
  DataTableRow,
  PageHeader,
  StatCard,
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { SparkBar } from "@/components/ui/SparkBar";
import {
  getTrader,
  formatUsd,
  formatPrice,
  formatTimeAgo,
  formatPct,
} from "@/lib/api";

interface Props {
  params: Promise<{ address: string }>;
}

export default async function TraderDetailPage({ params }: Props) {
  const { address } = await params;

  let trader;
  try {
    trader = await getTrader(decodeURIComponent(address));
  } catch {
    notFound();
  }

  return (
    <DashboardLayout>
      <PageHeader
        title={trader.alias}
        description={
          <Link
            href={`https://app.hyperliquid.xyz/explorer/address/${encodeURIComponent(
              trader.address,
            )}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 text-accent hover:underline"
          >
            {trader.address}
          </Link>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total PnL"
          value={formatUsd(trader.pnl_usd)}
          change={formatPct(trader.pnl_change_pct)}
          positive={trader.pnl_change_pct >= 0}
        />
        <StatCard
          label="Win Rate"
          value={trader.win_rate > 0 ? `${trader.win_rate}%` : "—"}
        />
        <StatCard
          label="Avg Hold Time"
          value={trader.avg_hold_hours > 0 ? `${trader.avg_hold_hours}h` : "—"}
        />
        <StatCard
          label="Total Trades"
          value={
            trader.total_trades > 0
              ? trader.total_trades.toLocaleString()
              : "—"
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 rounded-xl border border-border bg-bg-surface p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-3">
            Behavior Analysis
          </h3>
          <p className="text-sm text-text-muted leading-relaxed">
            {trader.behavior_summary}
          </p>
          <div className="flex gap-2 mt-4 flex-wrap">
            {trader.strategy_tags.map((tag) => (
              <Badge key={tag} variant="accent">
                {tag}
              </Badge>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-bg-surface p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-3">
            Performance Trend
          </h3>
          <SparkBar
            values={trader.sparkline}
            color={trader.pnl_change_pct >= 0 ? "positive" : "negative"}
            className="h-16 gap-1"
          />
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Risk Score</span>
              <span className="font-medium">{trader.risk_score}/100</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Rank</span>
              <span className="font-medium text-accent">#{trader.rank}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Preferred</span>
              <span className="font-medium">
                {trader.preferred_assets.join(", ")}
              </span>
            </div>
          </div>
        </div>
      </div>

      <h3 className="text-base font-semibold text-text-primary mb-4">
        Recent Trades
      </h3>
      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>Type</DataTableHeaderCell>
          <DataTableHeaderCell>Size</DataTableHeaderCell>
          <DataTableHeaderCell>Price</DataTableHeaderCell>
          <DataTableHeaderCell>Time</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {trader.recent_positions.map((pos, i) => (
            <DataTableRow key={i}>
              <DataTableCell className="font-medium">{pos.asset}</DataTableCell>
              <DataTableCell>
                <Badge variant={pos.side as "long" | "short"}>
                  {pos.side.toUpperCase()}
                </Badge>
              </DataTableCell>
              <DataTableCell>
                <Badge variant={pos.type as "entry" | "exit"}>
                  {pos.type.toUpperCase()}
                </Badge>
              </DataTableCell>
              <DataTableCell>{formatUsd(pos.size_usd)}</DataTableCell>
              <DataTableCell>
                {pos.price ? formatPrice(pos.price, pos.asset) : "—"}
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {formatTimeAgo(pos.timestamp)}
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <div className="mt-6">
        <Link
          href="/traders"
          className="text-sm text-accent hover:underline"
        >
          Back to all traders
        </Link>
      </div>
    </DashboardLayout>
  );
}
