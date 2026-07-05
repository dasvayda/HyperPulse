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
import { SparkBarBackground } from "@/components/ui/SparkBar";
import { InsightCard } from "@/components/ui/InsightCard";
import { AlertFeed } from "@/components/ui/AlertFeed";
import {
  getDashboardStats,
  getWhaleAlerts,
  getLiquidationZones,
  getRankings,
  getAIInsights,
  getAlertsHistory,
  getPipelineStatus,
  getMarketStatus,
  formatUsd,
  formatTimeAgo,
  formatConfidence,
} from "@/lib/api";

export default async function HomePage() {
  const [stats, alerts, zones, rankings, insights, alertHistory, pipeline, market] =
    await Promise.all([
      getDashboardStats(),
      getWhaleAlerts(),
      getLiquidationZones(),
      getRankings(),
      getAIInsights(),
      getAlertsHistory(),
      getPipelineStatus(),
      getMarketStatus(),
    ]);

  const recentAlerts = alerts.slice(0, 5);
  const topZones = zones.slice(0, 4);
  const topRanks = rankings.slice(0, 5);
  const previewInsights = insights.slice(0, 2);

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
          value={String(stats.active_whales)}
          change={`Provider: ${pipeline.ai_provider}`}
          positive
        />
        <StatCard
          label="Dominant Strategy"
          value={stats.dominant_strategy ?? "—"}
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
          <div
            className={
              previewInsights.length > 1
                ? "grid grid-cols-1 md:grid-cols-2 gap-4"
                : "grid grid-cols-1 gap-4"
            }
          >
            {previewInsights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} className="w-full" />
            ))}
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
          <AlertFeed alerts={alertHistory.slice(0, 4)} />
        </div>
      </div>

      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-text-primary">
            Smart Money Ranking
          </h2>
          <Link href="/rankings" className="text-xs text-accent hover:underline">
            Full ranking
          </Link>
        </div>
        <DataTable>
          <DataTableHead>
            <DataTableHeaderCell>#</DataTableHeaderCell>
            <DataTableHeaderCell>Trader</DataTableHeaderCell>
            <DataTableHeaderCell>Score</DataTableHeaderCell>
            <DataTableHeaderCell>Win Rate</DataTableHeaderCell>
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
                <DataTableCell className="text-positive">
                  {rank.win_rate}%
                </DataTableCell>
                <DataTableCell>
                  {formatConfidence(rank.momentum_score)}
                </DataTableCell>
                <DataTableCell>
                  <div className="flex gap-1 flex-wrap">
                    {rank.strategy_tags.slice(0, 2).map((tag) => (
                      <Badge key={tag} variant="accent">
                        {tag}
                      </Badge>
                    ))}
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
