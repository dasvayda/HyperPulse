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
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { SparkBarBackground } from "@/components/ui/SparkBar";
import { getRankings, formatUsd, formatConfidence } from "@/lib/api";

const SMART_MONEY_SCORE_HELP = (
  <>
    <p className="mb-2 font-medium text-text-primary">Live mode formula (0–100)</p>
    <ul className="mb-2 list-disc space-y-1 pl-4">
      <li>All-time PnL (log-normalized among peers): 35%</li>
      <li>All-time ROI / momentum: 30%</li>
      <li>PnL curve consistency (sparkline): 20%</li>
      <li>Risk adjustment (100 − risk score): 15%</li>
    </ul>
    <p className="text-text-dim">
      When fill-level win rate / trade counts exist, the score also blends win
      rate (20%) and reweights the other terms. Higher is better.
    </p>
  </>
);

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
          <DataTableHeaderCell>
            <InfoTooltip label="Smart Money Score">{SMART_MONEY_SCORE_HELP}</InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>All-time PnL</DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Open ROI">
              Current open-position ROI vs entry, side-aware and leverage-scaled.
              Portfolio value is margin-weighted (sum uPnL / sum notional÷leverage).
              Shows — when the trader has no priced open positions in the whale book.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Momentum">
              All-time ROI normalized against the current peer set (same input
              used at 30% weight in the live Smart Money Score).
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Consistency">
              Stability of the account / PnL sparkline (trend + low volatility).
              Used at 20% weight in the live Smart Money Score.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Risk">
              Higher = riskier. Score uses risk adjustment = 100 − risk (15%
              weight in live mode).
            </InfoTooltip>
          </DataTableHeaderCell>
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
                    {rank.open_unrealized_pnl_usd != null && (
                      <span className="text-xs text-text-dim">
                        {formatUsd(rank.open_unrealized_pnl_usd)}
                      </span>
                    )}
                  </div>
                ) : (
                  <span className="text-xs text-text-dim">—</span>
                )}
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
        Live formula: all-time PnL 35% + ROI/momentum 30% + curve consistency 20% +
        risk adjustment 15%. Hover the ⓘ next to Smart Money Score for details.
        All-time PnL $ is cumulative; green % under it is all-time ROI.
        Open ROI is current unrealized ROI on open positions (not win rate).
      </p>
    </DashboardLayout>
  );
}
