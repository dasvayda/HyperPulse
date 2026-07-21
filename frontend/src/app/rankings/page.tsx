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
import { getRankings, formatUsd, formatConfidence } from "@/lib/api";

export default async function RankingsPage() {
  const rankings = await getRankings();

  return (
    <DashboardLayout>
      <PageHeader
        title="Smart Money Ranking"
        description="Composite ranking from live Hyperliquid all-time PnL/ROI, curve stability, and risk"
      />

      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>#</DataTableHeaderCell>
          <DataTableHeaderCell>Trader</DataTableHeaderCell>
          <DataTableHeaderCell>Smart Money Score</DataTableHeaderCell>
          <DataTableHeaderCell>All-time PnL</DataTableHeaderCell>
          <DataTableHeaderCell>Win Rate</DataTableHeaderCell>
          <DataTableHeaderCell>Momentum</DataTableHeaderCell>
          <DataTableHeaderCell>Consistency</DataTableHeaderCell>
          <DataTableHeaderCell>Risk</DataTableHeaderCell>
          <DataTableHeaderCell>Strategy</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {rankings.map((rank) => (
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
                    {rank.address}
                  </span>
                </Link>
              </DataTableCell>
              <DataTableCell>
                <SparkBarBackground values={rank.sparkline}>
                  <span className="text-lg font-semibold text-accent">
                    {rank.smart_money_score}
                  </span>
                </SparkBarBackground>
              </DataTableCell>
              <DataTableCell>
                <TrendValue
                  value={formatUsd(rank.pnl_usd)}
                  pct={rank.pnl_change_pct}
                />
              </DataTableCell>
              <DataTableCell className="text-positive font-medium">
                {rank.win_rate > 0 ? `${rank.win_rate}%` : "—"}
              </DataTableCell>
              <DataTableCell>{formatConfidence(rank.momentum_score)}</DataTableCell>
              <DataTableCell>
                {formatConfidence(rank.consistency_score)}
              </DataTableCell>
              <DataTableCell>
                <div className="flex items-center gap-2">
                  <div className="w-10 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        rank.risk_score > 70
                          ? "bg-negative"
                          : rank.risk_score > 50
                            ? "bg-accent"
                            : "bg-positive"
                      }`}
                      style={{ width: `${rank.risk_score}%` }}
                    />
                  </div>
                  <span className="text-xs text-text-muted">{rank.risk_score}</span>
                </div>
              </DataTableCell>
              <DataTableCell>
                <div className="flex gap-1 flex-wrap">
                  {rank.inferred_strategy ? (
                    <Badge variant="accent">{rank.inferred_strategy}</Badge>
                  ) : rank.strategy_tags.length > 0 ? (
                    rank.strategy_tags.map((tag) => (
                      <Badge key={tag} variant="accent">
                        {tag}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-text-dim">—</span>
                  )}
                </div>
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <p className="text-xs text-text-dim mt-4">
        Live formula: all-time PnL 35% + ROI 30% + curve stability 20% + risk adjustment 15%.
        Dollar value is cumulative all-time PnL; green % is all-time ROI (not open-position PnL).
        Win rate is shown only when fill-level stats are available.
      </p>
    </DashboardLayout>
  );
}
