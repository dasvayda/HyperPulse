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
import { ScoreMeter, SwingLabel } from "@/components/ui/ScoreMeter";
import { getRankings, formatUsd, formatConfidence } from "@/lib/api";

const SMART_MONEY_SCORE_HELP = (
  <>
    <p className="mb-2 font-medium text-text-primary">
      Score out of 100 — bar fill = how close to max
    </p>
    <ul className="mb-2 list-disc space-y-1 pl-4">
      <li>All-time PnL (log-normalized among peers): 35%</li>
      <li>All-time ROI peer rank: 30%</li>
      <li>Day/Week/Month PnL stability: 20%</li>
      <li>ROI swing adjustment (steadier → higher): 15%</li>
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
        title="Smart Money"
        description="Top 15 accounts by asset size, ordered by Smart Money Score"
      />

      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>#</DataTableHeaderCell>
          <DataTableHeaderCell>Trader</DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Smart Money Score">
              {SMART_MONEY_SCORE_HELP}
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>Account Value</DataTableHeaderCell>
          <DataTableHeaderCell>All-time PnL</DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Open ROI">
              Current open-position ROI vs entry, side-aware and leverage-scaled.
              Portfolio value is margin-weighted (sum uPnL / sum notional÷leverage).
              Shows — when the trader has no priced open positions in the whale book.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="ROI peer">
              All-time ROI ranked vs other tracked whales (0–100). Not the
              absolute return %. Same input used at 30% weight in the live Smart
              Money Score.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Consistency">
              Stability of Day/Week/Month PnL (trend + low volatility).
              Used at 20% weight in the live Smart Money Score.
            </InfoTooltip>
          </DataTableHeaderCell>
          <DataTableHeaderCell>
            <InfoTooltip label="Swing">
              How jumpy Day / Week / Month / All-time ROI is across those
              windows. Low = steadier, High = big swings. Not leverage and not
              &quot;risk of ruin.&quot; (Multi-position leverage would need a
              size-weighted avg — shown on trader detail when we have opens.)
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
                    {rank.address.slice(0, 10)}…
                  </span>
                </Link>
              </DataTableCell>
              <DataTableCell>
                <ScoreMeter value={rank.smart_money_score} />
              </DataTableCell>
              <DataTableCell className="font-medium">
                {rank.account_value_usd != null
                  ? formatUsd(rank.account_value_usd)
                  : "—"}
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
                <SwingLabel riskScore={rank.risk_score} />
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
        Universe: top 15 traders by account value. Sort: Smart Money Score
        (PnL 35% + ROI peer 30% + consistency 20% + swing adj 15%). For Open
        ROI / PnL performance board, see Ranking.
      </p>
    </DashboardLayout>
  );
}
