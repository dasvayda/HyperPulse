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
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { WindowPnlBars } from "@/components/ui/SparkBar";
import {
  getPerformanceRankings,
  getPipelineStatus,
  formatUsd,
} from "@/lib/api";

export default async function RankingPage() {
  const [performance, pipeline] = await Promise.all([
    getPerformanceRankings(),
    getPipelineStatus(),
  ]);
  const { items, threshold_usd, target_count, base_threshold_usd } = performance;

  return (
    <DashboardLayout>
      <PageHeader
        title="Ranking"
        description="Open ROI and PnL among traders above an auto-tuned |PnL| or |uPnL| floor"
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
          <DataTableHeaderCell>
            <InfoTooltip label="Open ROI">
              Current open-position ROI (entry vs mark, leverage-scaled). Primary
              sort key for this list.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>All-time PnL</DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Open uPnL">
              Sum of unrealized PnL on open positions. Eligibility uses max(|PnL|,
              |uPnL|).
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>Account Value</DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="D / W / M">
              Day, Week, Month PnL from the Hyperliquid leaderboard — not an
              equity curve. Green = profit in that window, red = loss. Bar height
              compares those three only (all-time is the All-time PnL column).
            </InfoTooltip>
          </DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {items.map((rank) => (
            <DataTableRow key={rank.address}>
              <DataTableCell className="text-text-muted font-mono">
                {rank.rank}
              </DataTableCell>
              <DataTableCell>
                <Link
                  href={`/traders/${encodeURIComponent(rank.address)}`}
                  className="flex flex-col"
                >
                  <span className="text-accent hover:underline font-medium">
                    {rank.alias}
                  </span>
                  <span className="text-xs text-text-dim font-mono">
                    {rank.address.slice(0, 10)}…
                  </span>
                </Link>
              </DataTableCell>
              <DataTableCell>
                {rank.open_roi_pct != null ? (
                  <div className="flex flex-col">
                    <span
                      className={
                        rank.open_roi_pct >= 0
                          ? "text-positive font-medium"
                          : "text-negative font-medium"
                      }
                    >
                      {rank.open_roi_pct >= 0 ? "+" : ""}
                      {rank.open_roi_pct.toFixed(2)}%
                    </span>
                  </div>
                ) : (
                  <span className="text-xs text-text-dim">—</span>
                )}
              </DataTableCell>
              <DataTableCell>
                <TrendValue
                  value={formatUsd(rank.pnl_usd)}
                  pct={rank.pnl_change_pct}
                />
              </DataTableCell>
              <DataTableCell>
                {rank.open_unrealized_pnl_usd != null ? (
                  <span
                    className={
                      rank.open_unrealized_pnl_usd >= 0
                        ? "text-positive font-medium"
                        : "text-negative font-medium"
                    }
                  >
                    {formatUsd(rank.open_unrealized_pnl_usd)}
                  </span>
                ) : (
                  <span className="text-xs text-text-dim">—</span>
                )}
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {rank.account_value_usd != null
                  ? formatUsd(rank.account_value_usd)
                  : "—"}
              </DataTableCell>
              <DataTableCell>
                <WindowPnlBars values={rank.sparkline} />
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <p className="text-xs text-text-dim mt-4">
        Inclusion: max(|all-time PnL|, |open uPnL|) ≥ {formatUsd(threshold_usd)}{" "}
        (auto-tuned near {formatUsd(base_threshold_usd)} so ~{target_count} names
        appear). Sorted by Open ROI, then all-time PnL. Smart Money (large-account
        score board) lives under Smart Money in the sidebar.
      </p>
    </DashboardLayout>
  );
}
