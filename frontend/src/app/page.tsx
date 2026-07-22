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
  StatCard,
  AssetIcon,
  TrendValue,
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { SparkBarBackground } from "@/components/ui/SparkBar";
import { InsightCard } from "@/components/ui/InsightCard";
import { AlertFeed } from "@/components/ui/AlertFeed";
import { WhaleBiasPanel } from "@/components/ui/WhaleBiasPanel";
import {
  getDashboardStats,
  getWhaleAlerts,
  getLiquidationZones,
  getRankings,
  getAIInsights,
  getAlertsHistory,
  getPipelineStatus,
  getMarketStatus,
  getCoinPulse,
  getBiggestPositions,
  getWhaleBookSummary,
  formatUsd,
  formatTimeAgo,
  formatConfidence,
  formatPct,
  formatFundingPct,
  formatPrice,
} from "@/lib/api";

export default async function HomePage() {
  const [
    stats,
    alerts,
    zones,
    rankings,
    insights,
    alertHistory,
    pipeline,
    market,
    coinPulse,
    whaleSummary,
    biggestPositions,
  ] = await Promise.all([
    getDashboardStats(),
    getWhaleAlerts(),
    getLiquidationZones(),
    getRankings(),
    getAIInsights(),
    getAlertsHistory(),
    getPipelineStatus(),
    getMarketStatus(),
    getCoinPulse(),
    getWhaleBookSummary(),
    getBiggestPositions(8),
  ]);

  const recentAlerts = alerts.slice(0, 5);
  const topZones = zones.slice(0, 4);
  const topRanks = rankings.slice(0, 5);
  // Prefer multi-signal coin stance cards (BL-02) over book-wide / style-mix context.
  const coinStanceInsights = insights.filter(
    (insight) =>
      Boolean(insight.asset) &&
      insight.signals.some((s) => s.startsWith("Whale L/S:")) &&
      insight.signals.some(
        (s) => s.startsWith("Funding:") || s.startsWith("Liq 24h:")
      )
  );
  const previewInsights =
    coinStanceInsights.length > 0
      ? coinStanceInsights.slice(0, 1)
      : insights.slice(0, 1);
  const pulse = coinPulse.slice(0, 10);
  const maxOiUsd = Math.max(
    ...pulse.map((row) => row.open_interest_usd ?? 0),
    1
  );

  return (
    <DashboardLayout>
      <PageHeader
        title="Dashboard"
        description="AI strategy inference, smart money ranking, and liquidation intelligence"
        actions={
          <span className="text-xs text-text-dim border border-border rounded-full px-3 py-1">
            Data source: {stats.data_source ?? pipeline.data_source}
          </span>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Active Whales"
          value={
            stats.whales_positioned != null
              ? `${stats.whales_positioned}/${stats.active_whales}`
              : String(stats.active_whales)
          }
          change={
            stats.whale_long_pct != null
              ? `By $ size · L ${stats.whale_long_pct.toFixed(0)}% / S ${Math.max(0, 100 - stats.whale_long_pct).toFixed(0)}%`
              : `Provider: ${pipeline.ai_provider}`
          }
        />
        <StatCard
          label="Whale Bias"
          value={(stats.whale_net_bias ?? stats.dominant_strategy ?? "—").toUpperCase()}
          change={`${pipeline.inferences_count} inferences`}
          positive
        />
        <StatCard
          label="Avg Smart Money"
          value={
            stats.avg_smart_money_score != null
              ? String(stats.avg_smart_money_score)
              : "—"
          }
          change="Composite score"
          positive
        />
        <StatCard
          label="Telegram Alerts"
          value={String(stats.telegram_alerts_24h ?? alertHistory.length)}
          change={
            pipeline.telegram_configured ? "Bot connected" : "Queued locally"
          }
          positive={pipeline.telegram_configured}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        <div className="rounded-xl border border-border bg-bg-surface p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-3">
            Hyperliquid Market Status
          </h2>
          <dl className="space-y-1 text-xs text-text-muted">
            <div className="flex justify-between">
              <dt>Top asset</dt>
              <dd className="text-text-primary">
                {market.top_asset ?? stats.top_asset}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt>Last snapshot</dt>
              <dd>
                {market.last_snapshot_at
                  ? formatTimeAgo(market.last_snapshot_at)
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt>Last liquidation</dt>
              <dd>
                {market.last_liquidation_at
                  ? formatTimeAgo(market.last_liquidation_at)
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt>Liquidations (24h)</dt>
              <dd>{market.liquidation_events_24h}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Source</dt>
              <dd className={market.has_live_market ? "text-positive" : ""}>
                {market.has_live_market ? "live" : "no data yet"}
              </dd>
            </div>
          </dl>
        </div>
        <div className="rounded-xl border border-border bg-bg-surface p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-3">
            Pipeline Status
          </h2>
          <dl className="space-y-1 text-xs text-text-muted">
            <div className="flex justify-between">
              <dt>Collectors</dt>
              <dd>
                {pipeline.last_collect_at
                  ? formatTimeAgo(pipeline.last_collect_at)
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt>Inference</dt>
              <dd>
                {pipeline.last_inference_at
                  ? formatTimeAgo(pipeline.last_inference_at)
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt>Ranking</dt>
              <dd>
                {pipeline.last_ranking_at
                  ? formatTimeAgo(pipeline.last_ranking_at)
                  : "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt>Tracked traders</dt>
              <dd>{pipeline.traders_tracked}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Inferences</dt>
              <dd>{pipeline.inferences_count}</dd>
            </div>
            <div className="flex justify-between">
              <dt>Alerts</dt>
              <dd>{pipeline.alerts_count}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-text-primary">
              AI Market Insights
            </h2>
            <Link href="/insights" className="text-xs text-accent hover:underline">
              View all
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <WhaleBiasPanel summary={whaleSummary} />
            {previewInsights.length > 0 ? (
              previewInsights.map((insight) => (
                  <InsightCard key={insight.id} insight={insight} className="w-full" />
                ))
            ) : (
              <div className="rounded-xl border border-border border-dashed bg-bg-surface/50 p-5 flex items-center justify-center text-center">
                <p className="text-sm text-text-dim">
                  Coin stance cards appear after whale book + funding/liq signals are ready.
                </p>
              </div>
            )}
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-text-primary">
              Alert Feed
            </h2>
            <Link href="/alerts" className="text-xs text-accent hover:underline">
              History
            </Link>
          </div>
          <AlertFeed alerts={alertHistory.slice(0, 3)} />
        </div>
      </div>

      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-text-primary">Coin Pulse</h2>
            <p className="text-xs text-text-dim mt-1">
              Top markets by 24h notional volume (includes HIP/xyz names when active)
            </p>
          </div>
        </div>
        <DataTable>
          <DataTableHead>
            <DataTableHeaderCell>Perp</DataTableHeaderCell>
            <DataTableHeaderCell>Last</DataTableHeaderCell>
            <DataTableHeaderCell>24h Vol</DataTableHeaderCell>
            <DataTableHeaderCell>Open Interest</DataTableHeaderCell>
            <DataTableHeaderCell>Funding</DataTableHeaderCell>
            <DataTableHeaderCell>Liq 24h</DataTableHeaderCell>
            <DataTableHeaderCell>Whale OI</DataTableHeaderCell>
            <DataTableHeaderCell>Whale Bias</DataTableHeaderCell>
          </DataTableHead>
          <DataTableBody>
            {pulse.map((row) => {
              const change = row.change_pct_24h;
              const funding = row.funding_rate;
              const fundingClass =
                funding == null
                  ? "text-text-dim"
                  : funding > 0
                    ? "text-negative"
                    : funding < 0
                      ? "text-positive"
                      : "text-text-muted";
              const bias = row.whale_bias_label;
              const biasClass =
                bias == null
                  ? "text-text-dim"
                  : bias.includes("long")
                    ? "text-positive"
                    : bias.includes("short")
                      ? "text-negative"
                      : "text-text-muted";
              const oiUsd = row.open_interest_usd ?? 0;
              const oiWidth = Math.max(6, Math.round((oiUsd / maxOiUsd) * 100));
              const timeline = row.liq_timeline ?? [];
              const timelineMax = Math.max(
                ...timeline.map((b) => b.long + b.short),
                1
              );
              const liqLong = row.liq_long_usd_24h ?? 0;
              const liqShort = row.liq_short_usd_24h ?? 0;
              const liqTotal = liqLong + liqShort;
              return (
                <DataTableRow key={row.asset}>
                  <DataTableCell>
                    <div className="flex items-center gap-2">
                      <AssetIcon asset={row.asset} />
                      {row.asset_tag && (
                        <Badge variant="accent" className="text-[10px] uppercase">
                          {row.asset_tag}
                        </Badge>
                      )}
                    </div>
                  </DataTableCell>
                  <DataTableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm text-text-primary">
                        {row.mark_price != null
                          ? formatPrice(row.mark_price, row.asset)
                          : "—"}
                      </span>
                      <span
                        className={`text-xs ${
                          change == null
                            ? "text-text-dim"
                            : change >= 0
                              ? "text-positive"
                              : "text-negative"
                        }`}
                      >
                        {change != null ? formatPct(change) : "—"}
                      </span>
                    </div>
                  </DataTableCell>
                  <DataTableCell className="text-sm text-text-primary">
                    {row.day_volume_usd != null && row.day_volume_usd > 0
                      ? formatUsd(row.day_volume_usd)
                      : "—"}
                  </DataTableCell>
                  <DataTableCell>
                    <div className="flex flex-col gap-1 min-w-[88px]">
                      <span className="text-sm text-text-primary">
                        {oiUsd > 0 ? formatUsd(oiUsd) : "—"}
                      </span>
                      <div className="h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                        <div
                          className="h-full rounded-full bg-accent/70"
                          style={{ width: `${oiWidth}%` }}
                        />
                      </div>
                    </div>
                  </DataTableCell>
                  <DataTableCell className={`text-xs font-medium ${fundingClass}`}>
                    {funding != null ? formatFundingPct(funding) : "—"}
                  </DataTableCell>
                  <DataTableCell>
                    <div
                      className="flex flex-col gap-1 min-w-[96px]"
                      title={
                        liqTotal > 0
                          ? `24h liq · long ${formatUsd(liqLong)} / short ${formatUsd(liqShort)} · bars = 4h windows (left older → right newer)`
                          : "No liquidations in the last 24h"
                      }
                    >
                      <div className="flex items-end gap-[3px] h-4">
                        {(timeline.length > 0 ? timeline : Array.from({ length: 6 }, () => ({ long: 0, short: 0 }))).map(
                          (bucket, i) => {
                            const total = bucket.long + bucket.short;
                            const height =
                              total <= 0
                                ? 2
                                : Math.max(4, Math.round((total / timelineMax) * 16));
                            const tone =
                              total <= 0
                                ? "bg-border/50"
                                : bucket.long >= bucket.short * 1.25
                                  ? "bg-negative"
                                  : bucket.short >= bucket.long * 1.25
                                    ? "bg-positive"
                                    : "bg-text-muted/70";
                            return (
                              <div
                                key={`${row.asset}-liq-${i}`}
                                className={`w-1.5 rounded-sm ${tone}`}
                                style={{ height }}
                              />
                            );
                          }
                        )}
                      </div>
                      <span className="text-[11px] text-text-dim leading-none">
                        {liqTotal > 0
                          ? liqLong >= liqShort * 1.25
                            ? `Long ${formatUsd(liqLong)}`
                            : liqShort >= liqLong * 1.25
                              ? `Short ${formatUsd(liqShort)}`
                              : `Mixed ${formatUsd(liqTotal)}`
                          : "Quiet"}
                      </span>
                    </div>
                  </DataTableCell>
                  <DataTableCell className="text-xs text-text-muted">
                    {row.whale_oi_pct != null
                      ? `${row.whale_oi_pct.toFixed(1)}%`
                      : "—"}
                  </DataTableCell>
                  <DataTableCell>
                    {row.whale_long_pct != null ? (
                      <div className="flex items-baseline gap-2 whitespace-nowrap">
                        <span className={`text-xs font-medium ${biasClass}`}>
                          {bias ?? "Balanced"}
                        </span>
                        <span className="text-[11px] text-text-dim">
                          L{row.whale_long_pct.toFixed(0)}%
                          {row.whale_net_notional_usd != null
                            ? ` · ${
                                row.whale_net_notional_usd >= 0 ? "+" : "-"
                              }${formatUsd(Math.abs(row.whale_net_notional_usd))}`
                            : ""}
                        </span>
                      </div>
                    ) : (
                      <span className="text-xs text-text-dim">—</span>
                    )}
                  </DataTableCell>
                </DataTableRow>
              );
            })}
          </DataTableBody>
        </DataTable>
      </div>

      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-text-primary">
              Biggest Positions
            </h2>
            <p className="text-xs text-text-dim mt-1">
              Tracked whales only · ranked by open notional (not full-network)
            </p>
          </div>
        </div>
        <DataTable>
          <DataTableHead>
            <DataTableHeaderCell>#</DataTableHeaderCell>
            <DataTableHeaderCell>Trader</DataTableHeaderCell>
            <DataTableHeaderCell>Asset</DataTableHeaderCell>
            <DataTableHeaderCell>Side</DataTableHeaderCell>
            <DataTableHeaderCell>Notional</DataTableHeaderCell>
            <DataTableHeaderCell>Entry</DataTableHeaderCell>
            <DataTableHeaderCell>uPnL / ROI</DataTableHeaderCell>
          </DataTableHead>
          <DataTableBody>
            {biggestPositions.length > 0 ? (
              biggestPositions.map((pos) => (
                <DataTableRow key={`${pos.trader_address}-${pos.asset}-${pos.side}-${pos.rank}`}>
                  <DataTableCell className="text-text-muted font-mono">
                    {pos.rank}
                  </DataTableCell>
                  <DataTableCell>
                    <Link
                      href={`/traders/${encodeURIComponent(pos.trader_address)}`}
                      className="text-sm text-accent hover:underline"
                    >
                      {pos.trader_alias}
                    </Link>
                  </DataTableCell>
                  <DataTableCell>
                    <AssetIcon asset={pos.asset} />
                  </DataTableCell>
                  <DataTableCell>
                    <Badge variant={pos.side}>{pos.side.toUpperCase()}</Badge>
                  </DataTableCell>
                  <DataTableCell className="text-sm text-text-primary">
                    {formatUsd(pos.size_usd)}
                    <span className="block text-[11px] text-text-dim">
                      {pos.leverage.toFixed(1)}x
                    </span>
                  </DataTableCell>
                  <DataTableCell className="text-sm text-text-muted">
                    {formatPrice(pos.entry_price, pos.asset)}
                  </DataTableCell>
                  <DataTableCell>
                    {pos.unrealized_pnl_usd != null ? (
                      <div className="flex flex-col gap-0.5">
                        <span
                          className={`text-sm font-medium ${
                            pos.unrealized_pnl_usd >= 0
                              ? "text-positive"
                              : "text-negative"
                          }`}
                        >
                          {formatUsd(pos.unrealized_pnl_usd)}
                        </span>
                        {pos.roi_pct != null && (
                          <span
                            className={`text-xs ${
                              pos.roi_pct >= 0 ? "text-positive" : "text-negative"
                            }`}
                          >
                            {pos.roi_pct >= 0 ? "+" : ""}
                            {pos.roi_pct.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-text-dim">—</span>
                    )}
                  </DataTableCell>
                </DataTableRow>
              ))
            ) : (
              <DataTableRow>
                <DataTableCell className="text-text-dim">
                  Whale book still warming up — biggest positions appear after the
                  next collect cycle.
                </DataTableCell>
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
      </div>

      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text-primary">
            Smart Money
          </h2>
          <Link href="/rankings" className="text-xs text-accent hover:underline">
            Top 15 by size
          </Link>
        </div>
        <DataTable>
          <DataTableHead>
            <DataTableHeaderCell>#</DataTableHeaderCell>
            <DataTableHeaderCell>Trader</DataTableHeaderCell>
            <DataTableHeaderCell>
              <InfoTooltip label="Score">
                <p className="mb-1 font-medium text-text-primary">Smart Money Score</p>
                <p>
                  Live: PnL 35% + ROI/momentum 30% + consistency 20% + risk adj 15%.
                  Hover ⓘ on the full rankings page for the complete breakdown.
                </p>
              </InfoTooltip>
            </DataTableHeaderCell>
            <DataTableHeaderCell>
              <InfoTooltip label="Open ROI">
                Current open-position ROI (entry vs mark, leverage-scaled).
              </InfoTooltip>
            </DataTableHeaderCell>
            <DataTableHeaderCell>Momentum</DataTableHeaderCell>
            <DataTableHeaderCell>Strategy</DataTableHeaderCell>
          </DataTableHead>
          <DataTableBody>
            {topRanks.map((rank) => (
              <DataTableRow key={rank.address}>
                <DataTableCell className="text-text-muted font-mono">
                  {rank.rank}
                </DataTableCell>
                <DataTableCell>
                  <Link
                    href={`/traders/${encodeURIComponent(rank.address)}`}
                    className="text-accent hover:underline font-medium"
                  >
                    {rank.alias}
                  </Link>
                </DataTableCell>
                <DataTableCell>
                  <SparkBarBackground values={rank.sparkline}>
                    <span className="font-semibold text-accent">
                      {rank.smart_money_score}
                    </span>
                  </SparkBarBackground>
                </DataTableCell>
                <DataTableCell>
                  {rank.open_roi_pct != null ? (
                    <span
                      className={
                        rank.open_roi_pct >= 0
                          ? "text-positive font-medium"
                          : "text-negative font-medium"
                      }
                    >
                      {rank.open_roi_pct >= 0 ? "+" : ""}
                      {rank.open_roi_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="text-xs text-text-dim">—</span>
                  )}
                </DataTableCell>
                <DataTableCell>
                  {formatConfidence(rank.momentum_score)}
                </DataTableCell>
                <DataTableCell>
                  <div className="flex gap-1 flex-wrap">
                    {rank.inferred_strategy ? (
                      <Badge variant="accent">{rank.inferred_strategy}</Badge>
                    ) : rank.strategy_tags.length > 0 ? (
                      rank.strategy_tags.slice(0, 2).map((tag) => (
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
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-text-primary">
              Recent Whale Alerts
            </h2>
            <Link
              href="/whale-alerts"
              className="text-xs text-accent hover:underline"
            >
              View all
            </Link>
          </div>
          <DataTable>
            <DataTableHead>
              <DataTableHeaderCell>Trader</DataTableHeaderCell>
              <DataTableHeaderCell>Asset</DataTableHeaderCell>
              <DataTableHeaderCell>Action</DataTableHeaderCell>
              <DataTableHeaderCell>Size</DataTableHeaderCell>
              <DataTableHeaderCell>Time</DataTableHeaderCell>
            </DataTableHead>
            <DataTableBody>
              {recentAlerts.map((alert) => (
                <DataTableRow key={alert.id}>
                  <DataTableCell>
                    <Link
                      href={`/traders/${encodeURIComponent(alert.trader_address)}`}
                      className="text-accent hover:underline font-medium"
                    >
                      {alert.trader_alias}
                    </Link>
                  </DataTableCell>
                  <DataTableCell>
                    <AssetIcon asset={alert.asset} />
                  </DataTableCell>
                  <DataTableCell>
                    <Badge variant={alert.alert_type}>
                      {alert.side.toUpperCase()}{" "}
                      {alert.alert_type.toUpperCase()}
                    </Badge>
                  </DataTableCell>
                  <DataTableCell>{formatUsd(alert.size_usd)}</DataTableCell>
                  <DataTableCell className="text-text-muted">
                    {formatTimeAgo(alert.timestamp)}
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </div>

        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-text-primary">
              Liquidation Zones
            </h2>
            <Link
              href="/liquidations"
              className="text-xs text-accent hover:underline"
            >
              View all
            </Link>
          </div>
          <DataTable>
            <DataTableHead>
              <DataTableHeaderCell>Asset</DataTableHeaderCell>
              <DataTableHeaderCell>Price</DataTableHeaderCell>
              <DataTableHeaderCell>Side</DataTableHeaderCell>
              <DataTableHeaderCell>Size</DataTableHeaderCell>
            </DataTableHead>
            <DataTableBody>
              {topZones.map((zone) => (
                <DataTableRow key={zone.id}>
                  <DataTableCell>
                    <AssetIcon asset={zone.asset} />
                  </DataTableCell>
                  <DataTableCell>
                    <TrendValue
                      value={`$${zone.price.toLocaleString()}`}
                      pct={zone.distance_pct}
                    />
                  </DataTableCell>
                  <DataTableCell>
                    <Badge variant={zone.side}>
                      {zone.side.toUpperCase()} LIQ
                    </Badge>
                  </DataTableCell>
                  <DataTableCell>
                    <SparkBarBackground values={zone.sparkline}>
                      <span className="font-medium">
                        {formatUsd(zone.size_usd)}
                      </span>
                    </SparkBarBackground>
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </div>
      </div>
    </DashboardLayout>
  );
}
