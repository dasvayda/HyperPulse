import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge } from "@/components/ui/Badge";
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
import { PaperEquityChart } from "@/components/ui/PaperEquityChart";
import { PaperPortfolioCard } from "@/components/ui/PaperPortfolioCard";
import {
  formatPct,
  formatPrice,
  formatTimeAgo,
  formatUsd,
  getPaperEquity,
  getPaperPortfolioSummary,
  getPaperStrategy,
  getPaperTrades,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function PerformancePage() {
  const [summary, equity, trades, strategy] = await Promise.all([
    getPaperPortfolioSummary(),
    getPaperEquity(),
    getPaperTrades(),
    getPaperStrategy(),
  ]);

  const netCosts =
    summary.cumulative_fees +
    summary.cumulative_slippage -
    summary.cumulative_funding;

  return (
    <DashboardLayout>
      <PageHeader
        title="Paper Portfolio"
        description="What $1,000 would look like when Top 5 Whale signals are followed by fixed rules"
        actions={<Badge variant="accent">FORWARD TEST · v{strategy.version}</Badge>}
      />

      <div className="mb-6">
        <PaperPortfolioCard summary={summary} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Net return"
          value={formatPct(summary.return_pct)}
          change={`Started with ${formatUsd(summary.initial_cash)}`}
          positive={summary.return_pct >= 0}
        />
        <StatCard
          label="BTC hold"
          value={
            summary.benchmark_return_pct == null
              ? "—"
              : formatPct(summary.benchmark_return_pct)
          }
          change="Same start time and price source"
          positive={
            summary.benchmark_return_pct == null
              ? undefined
              : summary.benchmark_return_pct >= 0
          }
        />
        <StatCard
          label="Max drawdown"
          value={formatPct(summary.max_drawdown_pct)}
          change={`${summary.fully_closed_positions_count ?? 0} fully closed positions`}
          positive={summary.max_drawdown_pct === 0 ? undefined : false}
        />
        <StatCard
          label="Estimated costs"
          value={`$${netCosts.toFixed(2)}`}
          change={`Fees $${summary.cumulative_fees.toFixed(2)} · funding $${summary.cumulative_funding.toFixed(2)}`}
        />
      </div>

      <section className="mb-8">
        <div className="flex items-end justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-text-primary">Equity curve</h2>
            <p className="text-xs text-text-dim mt-1">
              Net NAV after fees, slippage and funding vs BTC buy-and-hold
            </p>
          </div>
          <p className="text-xs text-text-dim">Updated {formatTimeAgo(summary.updated_at)}</p>
        </div>
        <PaperEquityChart points={equity} />
      </section>

      <section className="mb-8">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-text-primary">Latest decisions</h2>
          <p className="text-xs text-text-dim mt-1">
            Top 5 position → recent Top 5 flow → 1h/4h trend confirmation
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {summary.last_decisions.length > 0 ? (
            summary.last_decisions.map((decision) => (
              <div key={decision.asset} className="rounded-xl border border-border bg-bg-surface p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-text-primary">{decision.asset}</h3>
                  <Badge variant={decision.action === "long" ? "long" : decision.action === "short" ? "short" : "hold"}>
                    {decision.action.toUpperCase()}
                  </Badge>
                </div>
                <dl className="mt-4 space-y-2 text-xs">
                  <DecisionRow label="Top 5 positions" value={decision.position_signal} />
                  <DecisionRow label="Recent Top 5 flow" value={decision.flow_signal} />
                  <DecisionRow label="Market trend" value={decision.trend} />
                  <DecisionRow label="Target" value={`${decision.target_weight_pct.toFixed(0)}%`} />
                </dl>
                <p className="mt-3 text-xs leading-relaxed text-text-muted">{decision.reason}</p>
              </div>
            ))
          ) : (
            <div className="md:col-span-3 rounded-xl border border-dashed border-border p-6 text-sm text-text-dim">
              The first hourly decision will appear after whale and 4h market snapshots are ready.
            </div>
          )}
        </div>
      </section>

      <section className="mb-8">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-text-primary">Open paper positions</h2>
          <p className="text-xs text-text-dim mt-1">No leverage above 1× · maximum 40% per asset</p>
        </div>
        <DataTable>
          <DataTableHead>
            <DataTableHeaderCell>Asset</DataTableHeaderCell>
            <DataTableHeaderCell>Side</DataTableHeaderCell>
            <DataTableHeaderCell>Weight</DataTableHeaderCell>
            <DataTableHeaderCell>Entry / Mark</DataTableHeaderCell>
            <DataTableHeaderCell>uPnL</DataTableHeaderCell>
          </DataTableHead>
          <DataTableBody>
            {summary.current_positions.length > 0 ? (
              summary.current_positions.map((position) => (
                <DataTableRow key={position.asset}>
                  <DataTableCell className="font-medium text-text-primary">{position.asset}</DataTableCell>
                  <DataTableCell><Badge variant={position.direction}>{position.direction.toUpperCase()}</Badge></DataTableCell>
                  <DataTableCell>{position.weight_pct.toFixed(1)}% · {formatUsd(position.notional_usd)}</DataTableCell>
                  <DataTableCell>{formatPrice(position.average_entry, position.asset)} / {position.mark_price == null ? "—" : formatPrice(position.mark_price, position.asset)}</DataTableCell>
                  <DataTableCell className={position.unrealized_pnl_usd >= 0 ? "text-positive" : "text-negative"}>{formatUsd(position.unrealized_pnl_usd)}</DataTableCell>
                </DataTableRow>
              ))
            ) : (
              <DataTableRow>
                <DataTableCell className="text-text-dim">WAIT — no confirmed position</DataTableCell>
                <DataTableCell>—</DataTableCell><DataTableCell>—</DataTableCell><DataTableCell>—</DataTableCell><DataTableCell>—</DataTableCell>
              </DataTableRow>
            )}
          </DataTableBody>
        </DataTable>
      </section>

      <section className="mb-8">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-text-primary">All paper trades</h2>
          <p className="text-xs text-text-dim mt-1">No winning-trade filter · newest first</p>
        </div>
        <DataTable>
          <DataTableHead>
            <DataTableHeaderCell>Time</DataTableHeaderCell>
            <DataTableHeaderCell>Asset</DataTableHeaderCell>
            <DataTableHeaderCell>Action</DataTableHeaderCell>
            <DataTableHeaderCell>Notional</DataTableHeaderCell>
            <DataTableHeaderCell>Fill</DataTableHeaderCell>
            <DataTableHeaderCell>Fee / PnL</DataTableHeaderCell>
          </DataTableHead>
          <DataTableBody>
            {trades.length > 0 ? (
              trades.map((trade) => (
                <DataTableRow key={trade.id}>
                  <DataTableCell className="text-text-muted">{formatTimeAgo(trade.created_at)}</DataTableCell>
                  <DataTableCell className="font-medium text-text-primary">{trade.asset}</DataTableCell>
                  <DataTableCell><Badge variant={trade.side === "buy" ? "buy" : "sell"}>{trade.side.toUpperCase()} · {trade.action}</Badge></DataTableCell>
                  <DataTableCell>{formatUsd(trade.notional_usd)}</DataTableCell>
                  <DataTableCell>{formatPrice(trade.fill_price, trade.asset)}</DataTableCell>
                  <DataTableCell>{formatUsd(trade.fee_usd)} / <span className={trade.realized_pnl_usd >= 0 ? "text-positive" : "text-negative"}>{formatUsd(trade.realized_pnl_usd)}</span></DataTableCell>
                </DataTableRow>
              ))
            ) : (
              <DataTableRow>
                <DataTableCell className="text-text-dim">No confirmed trades yet</DataTableCell>
                <DataTableCell>—</DataTableCell><DataTableCell>—</DataTableCell><DataTableCell>—</DataTableCell><DataTableCell>—</DataTableCell><DataTableCell>—</DataTableCell>
              </DataTableRow>
            )}
          </DataTableBody>
        </DataTable>
      </section>

      <section className="rounded-xl border border-border bg-bg-surface p-5">
        <h2 className="text-sm font-semibold text-text-primary">Method and limitations</h2>
        <p className="mt-2 text-sm leading-relaxed text-text-muted">{summary.disclosure}</p>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-text-muted">
          <DecisionRow label="Strategy" value={strategy.strategy_id} />
          <DecisionRow label="Config hash" value={strategy.config_hash.slice(0, 12)} />
          <DecisionRow label="Started" value={new Date(strategy.started_at).toLocaleDateString()} />
        </div>
      </section>
    </DashboardLayout>
  );
}

function DecisionRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-text-dim">{label}</dt>
      <dd className="text-right font-medium text-text-primary uppercase">{value}</dd>
    </div>
  );
}
