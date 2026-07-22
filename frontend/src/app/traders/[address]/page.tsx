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
  ApiError,
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
  const decoded = decodeURIComponent(address);

  let trader;
  try {
    trader = await getTrader(decoded);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    return (
      <DashboardLayout>
        <PageHeader
          title="Trader unavailable"
          description={`Could not load profile for ${decoded}. Backend may be restarting — retry in a moment.`}
        />
        <Link href="/traders" className="text-sm text-accent hover:underline">
          Back to all traders
        </Link>
      </DashboardLayout>
    );
  }

  const openPositions = trader.open_positions ?? [];
  const openNotional = openPositions.reduce((sum, pos) => sum + pos.size_usd, 0);
  const unrealizedPnl = openPositions.reduce(
    (sum, pos) => sum + (pos.unrealized_pnl_usd ?? 0),
    0,
  );
  const hasUnrealized = openPositions.some((pos) => pos.unrealized_pnl_usd != null);

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
          label="Unrealized PnL"
          value={hasUnrealized ? formatUsd(unrealizedPnl) : "—"}
          change={
            hasUnrealized
              ? `${openPositions.length} open position${openPositions.length === 1 ? "" : "s"}`
              : "Waiting for mark prices"
          }
          positive={hasUnrealized ? unrealizedPnl >= 0 : undefined}
        />
        <StatCard
          label="All-time PnL"
          value={formatUsd(trader.pnl_usd)}
          change={formatPct(trader.pnl_change_pct)}
          positive={trader.pnl_change_pct >= 0}
        />
        <StatCard
          label="Open Notional"
          value={openPositions.length > 0 ? formatUsd(openNotional) : "—"}
          change={
            openPositions.length > 0
              ? `${openPositions.length} position${openPositions.length === 1 ? "" : "s"}`
              : "No live book yet"
          }
          positive={openPositions.length > 0}
        />
        <StatCard
          label="Account Value"
          value={
            trader.account_value_usd && trader.account_value_usd > 0
              ? formatUsd(trader.account_value_usd)
              : "—"
          }
          change="Hyperliquid account equity"
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
            {trader.inferred_strategy && (
              <Badge variant="accent">{trader.inferred_strategy}</Badge>
            )}
            {trader.inferred_trading_style && (
              <Badge variant="default">{trader.inferred_trading_style}</Badge>
            )}
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
              <span className="text-text-muted">Assets</span>
              <span className="font-medium">
                {trader.preferred_assets.join(", ") || "—"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <h3 className="text-base font-semibold text-text-primary mb-4">
        Open Positions
      </h3>
      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>Size</DataTableHeaderCell>
          <DataTableHeaderCell>Entry</DataTableHeaderCell>
          <DataTableHeaderCell>Mark</DataTableHeaderCell>
          <DataTableHeaderCell>ROI</DataTableHeaderCell>
          <DataTableHeaderCell>Unrealized PnL</DataTableHeaderCell>
          <DataTableHeaderCell>Leverage</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {openPositions.length > 0 ? (
            openPositions.map((pos) => (
              <DataTableRow key={`${pos.asset}-${pos.side}-${pos.entry_price}`}>
                <DataTableCell className="font-medium">{pos.asset}</DataTableCell>
                <DataTableCell>
                  <Badge variant={pos.side}>
                    {pos.side.toUpperCase()}
                  </Badge>
                </DataTableCell>
                <DataTableCell>{formatUsd(pos.size_usd)}</DataTableCell>
                <DataTableCell>
                  {pos.entry_price
                    ? formatPrice(pos.entry_price, pos.asset)
                    : "—"}
                </DataTableCell>
                <DataTableCell>
                  {pos.mark_price
                    ? formatPrice(pos.mark_price, pos.asset)
                    : "—"}
                </DataTableCell>
                <DataTableCell>
                  {pos.roi_pct != null ? (
                    <span
                      className={
                        pos.roi_pct >= 0 ? "text-positive font-medium" : "text-negative font-medium"
                      }
                    >
                      {pos.roi_pct >= 0 ? "+" : ""}
                      {pos.roi_pct.toFixed(2)}%
                    </span>
                  ) : (
                    "—"
                  )}
                </DataTableCell>
                <DataTableCell>
                  {pos.unrealized_pnl_usd != null ? (
                    <span
                      className={
                        pos.unrealized_pnl_usd >= 0
                          ? "text-positive font-medium"
                          : "text-negative font-medium"
                      }
                    >
                      {formatUsd(pos.unrealized_pnl_usd)}
                    </span>
                  ) : (
                    "—"
                  )}
                </DataTableCell>
                <DataTableCell>{pos.leverage.toFixed(1)}x</DataTableCell>
              </DataTableRow>
            ))
          ) : (
            <DataTableRow>
              <DataTableCell className="text-text-dim">
                No open positions in the current whale book for this trader.
              </DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
            </DataTableRow>
          )}
        </DataTableBody>
      </DataTable>
      <p className="text-xs text-text-dim mt-2 mb-2">
        ROI is entry-vs-mark price move, side-aware and scaled by leverage.
        Unrealized PnL is the open position profit/loss vs entry (not realized).
        Mark prices come from the latest Hyperliquid market snapshot.
      </p>

      <h3 className="text-base font-semibold text-text-primary mb-4 mt-10">
        Recent Whale Alerts
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
          {trader.recent_positions.length > 0 ? (
            trader.recent_positions.map((pos, i) => (
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
            ))
          ) : (
            <DataTableRow>
              <DataTableCell className="text-text-dim">
                No large entry/exit alerts yet for this trader.
              </DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
              <DataTableCell>—</DataTableCell>
            </DataTableRow>
          )}
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
