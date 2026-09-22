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
import { InsightCardCarousel } from "@/components/ui/InsightCardCarousel";
import { AlertFeed } from "@/components/ui/AlertFeed";
import { WhaleBiasPanel } from "@/components/ui/WhaleBiasPanel";
import { CohortBiasPanel } from "@/components/ui/CohortBiasPanel";
import { ScoreMeter } from "@/components/ui/ScoreMeter";
import { pulseChipLabel } from "@/components/ui/PulseBar";
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
  getMarketBrief,
  getCohortBias,
  getMarketPulse,
  getFearGreed,
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
    marketBrief,
    cohortBias,
    marketPulse,
    fearGreed,
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
    getMarketBrief(),
    getCohortBias(),
    getMarketPulse(),
    getFearGreed().catch(() => null),
  ]);

  const recentAlerts = alerts.slice(0, 5);
  const topZones = zones.slice(0, 4);
  const topRanks = rankings.slice(0, 5);
  // Prefer teaser carousel: coin stances first, then Extreme funding / Consensus / other.
  const coinStanceInsights = insights.filter(
    (insight) =>
      Boolean(insight.asset) &&
      insight.signals.some((s) => s.startsWith("Whale L/S:")) &&
      insight.signals.some(
        (s) => s.startsWith("Funding:") || s.startsWith("Liq 24h:")
      )
  );
  const fundingCallout = insights.find(
    (insight) => insight.title === "Extreme funding"
  );
  const consensusCard = insights.find((insight) =>
    insight.title.toLowerCase().startsWith("top3 consensus")
  );
  const seen = new Set<string>();
  const previewInsights: typeof insights = [];
  for (const card of [
    ...coinStanceInsights.slice(0, 3),
    fundingCallout,
    consensusCard,
    ...insights.filter(
      (i) =>
        !coinStanceInsights.includes(i) &&
        i !== fundingCallout &&
        i !== consensusCard
    ),
  ]) {
    if (!card || seen.has(card.id)) continue;
    seen.add(card.id);
    previewInsights.push(card);
    if (previewInsights.length >= 5) break;
  }
  const pulse = coinPulse.slice(0, 10);
  const maxOiUsd = Math.max(
    ...pulse.map((row) => row.open_interest_usd ?? 0),
    1
  );

  // Top-3 by HL volume × whale book — same universe as Consensus alerts.
  const top3Assets = coinPulse.slice(0, 3).map((row) => row.asset);
  let top3Long = 0;
  let top3Short = 0;
  const top3Used: string[] = [];
  for (const asset of top3Assets) {
    const book = whaleSummary?.by_asset?.[asset];
    if (!book) continue;
    top3Long += book.long_notional_usd;
    top3Short += book.short_notional_usd;
    top3Used.push(asset);
  }
  const top3Total = top3Long + top3Short;
  const top3LongPct = top3Total > 0 ? (top3Long / top3Total) * 100 : null;
  const top3ShortPct =
    top3LongPct != null ? Math.max(0, 100 - top3LongPct) : null;
  const top3Bias =
    top3LongPct == null
      ? "—"
      : top3LongPct >= 55
        ? "LONG"
        : top3LongPct <= 45
          ? "SHORT"
          : "MIXED";
  const top3ShareLabel =
    top3LongPct == null || top3ShortPct == null
      ? "No Top3 whale book yet"
      : top3Bias === "SHORT"
        ? `${top3ShortPct.toFixed(0)}% short · ${top3Used.join("/")}`
        : top3Bias === "LONG"
          ? `${top3LongPct.toFixed(0)}% long · ${top3Used.join("/")}`
          : `${top3LongPct.toFixed(0)}% long / ${top3ShortPct.toFixed(0)}% short · ${top3Used.join("/")}`;

  const liq1hLong = market.liq_1h_long_usd ?? 0;
  const liq1hShort = market.liq_1h_short_usd ?? 0;
  const liq1hTotal = market.liq_1h_total_usd ?? liq1hLong + liq1hShort;

  const fearGreedDelta =
    fearGreed?.yesterday_value != null
      ? fearGreed.value - fearGreed.yesterday_value
      : null;
  const fearGreedChange =
    fearGreed == null
      ? "CMC unavailable"
      : fearGreedDelta != null
        ? `${fearGreed.classification} · ${fearGreedDelta > 0 ? `+${fearGreedDelta}` : String(fearGreedDelta)} vs yesterday (${fearGreed.yesterday_value})`
        : `${fearGreed.classification} · CMC`;
  const fearGreedPositive =
    fearGreedDelta != null
      ? fearGreedDelta > 0
        ? true
        : fearGreedDelta < 0
          ? false
          : fearGreed?.positive ?? undefined
      : fearGreed?.positive ?? undefined;

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
          label="Whale Book"
          value={(stats.whale_net_bias ?? stats.dominant_strategy ?? "—").toUpperCase()}
          change={
            stats.whales_positioned != null && stats.whale_long_pct != null
              ? `${stats.whales_positioned}/${stats.active_whales} · L ${stats.whale_long_pct.toFixed(0)}% / S ${Math.max(0, 100 - stats.whale_long_pct).toFixed(0)}%`
              : stats.whales_positioned != null
                ? `${stats.whales_positioned}/${stats.active_whales} positioned`
                : `${stats.active_whales} tracked`
          }
          positive={
            (stats.whale_net_bias ?? "").toLowerCase() === "long"
              ? true
              : (stats.whale_net_bias ?? "").toLowerCase() === "short"
                ? false
                : undefined
          }
        />
        <StatCard
          label="Top3 Consensus"
          value={top3Bias}
          change={top3ShareLabel}
          positive={
            top3Bias === "LONG" ? true : top3Bias === "SHORT" ? false : undefined
          }
        />
        <StatCard
          label="1h Liquidations"
          value={liq1hTotal > 0 ? formatUsd(liq1hTotal) : "$0"}
          details={[
            { label: "Longs", value: formatUsd(liq1hLong), tone: "negative" },
            { label: "Shorts", value: formatUsd(liq1hShort), tone: "positive" },
          ]}
        />
        <StatCard
          label="Fear & Greed"
          value={fearGreed ? String(fearGreed.value) : "—"}
          change={fearGreedChange}
          positive={fearGreedPositive}
        />
      </div>

      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-text-primary">
              Market Pulse
            </h2>
            <p className="text-xs text-text-dim mt-1">
              Top markets by volume ({marketPulse.scope}) · short Δ vs ~1h ago
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard
            label="Open Interest"
            value={marketPulse.oi_usd > 0 ? formatUsd(marketPulse.oi_usd) : "—"}
            change={
              marketPulse.oi_delta_pct != null
                ? formatPct(marketPulse.oi_delta_pct)
                : "No prior snapshot yet"
            }
            positive={
              marketPulse.oi_delta_pct == null
                ? undefined
                : marketPulse.oi_delta_pct >= 0
            }
          />
          <StatCard
            label="24h Volume"
            value={
              marketPulse.vol_usd_24h > 0
                ? formatUsd(marketPulse.vol_usd_24h)
                : "—"
            }
            change={
              marketPulse.vol_delta_pct != null
                ? formatPct(marketPulse.vol_delta_pct)
                : "No prior snapshot yet"
            }
            positive={
              marketPulse.vol_delta_pct == null
                ? undefined
                : marketPulse.vol_delta_pct >= 0
            }
          />
          <StatCard
            label="24h Liquidations"
            value={
              marketPulse.liq_usd_24h > 0
                ? formatUsd(marketPulse.liq_usd_24h)
                : "$0"
            }
            change={
              marketPulse.liq_delta_pct != null
                ? `1h vs avg hour ${formatPct(marketPulse.liq_delta_pct)}`
                : market.liq_24h_pressure || "sampled liq quiet"
            }
            positive={
              marketPulse.liq_delta_pct == null
                ? undefined
                : marketPulse.liq_delta_pct <= 0
            }
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8 items-start">
        <div className="lg:col-span-2 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-text-primary">
              AI Market Insights
            </h2>
            <Link href="/insights" className="text-xs text-accent hover:underline">
              Full brief
            </Link>
          </div>
          <Link
            href="/insights"
            className="mb-4 block rounded-xl border border-border bg-bg-elevated/40 px-4 py-3 hover:border-accent/40 transition-colors"
          >
            <p className="text-[10px] uppercase tracking-wide text-text-dim mb-1">
              Market Brief
            </p>
            <p className="text-sm font-medium text-text-primary line-clamp-2">
              {marketBrief.tldr?.now || marketBrief.headline}
            </p>
            {marketBrief.pulse ? (
              <p className="mt-1.5 text-xs text-text-dim">
                {pulseChipLabel(marketBrief.pulse)}
              </p>
            ) : null}
          </Link>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1 items-stretch">
            <WhaleBiasPanel summary={whaleSummary} className="h-full" />
            <InsightCardCarousel
              insights={previewInsights}
              className="h-full min-h-[200px]"
            />
          </div>
          <div className="mt-4">
            <CohortBiasPanel data={cohortBias} />
          </div>
        </div>
        <div className="flex flex-col min-h-0">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-text-primary">
              Alert Feed
            </h2>
            <Link href="/alerts" className="text-xs text-accent hover:underline">
              More
            </Link>
          </div>
          <AlertFeed alerts={alertHistory} limit={6} />
          {alertHistory.length > 6 ? (
            <Link
              href="/alerts"
              className="mt-3 text-xs text-accent hover:underline self-end"
            >
              More alerts
            </Link>
          ) : null}
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
              const bias = row.whale_bias_label;
              const biasClass =
                bias == null
                  ? "text-text-dim"
                  : bias.toLowerCase().includes("long")
                    ? "text-positive"
                    : bias.toLowerCase().includes("short")
                      ? "text-negative"
                      : "text-text-muted";
              const oiUsd = row.open_interest_usd ?? 0;
              const oiWidth = Math.max(6, Math.round((oiUsd / maxOiUsd) * 100));
              const liqLong = row.liq_long_usd_24h ?? 0;
              const liqShort = row.liq_short_usd_24h ?? 0;
              const liqTotal = liqLong + liqShort;
              const liqLongPct =
                liqTotal > 0 ? (liqLong / liqTotal) * 100 : 0;
              const liqShortPct =
                liqTotal > 0 ? Math.max(0, 100 - liqLongPct) : 0;
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
                  <DataTableCell>
                    {funding == null ? (
                      <span className="text-xs text-text-dim">—</span>
                    ) : (
                      <div
                        className="flex flex-col gap-0.5"
                        title={
                          funding > 0
                            ? "Positive funding: longs pay shorts"
                            : funding < 0
                              ? "Negative funding: shorts pay longs"
                              : "Flat funding"
                        }
                      >
                        <span className="text-xs font-medium tabular-nums text-text-primary">
                          {formatFundingPct(funding)}
                        </span>
                        <span className="text-[10px] leading-none text-text-dim">
                          {funding > 0
                            ? "Longs pay"
                            : funding < 0
                              ? "Shorts pay"
                              : "Flat"}
                        </span>
                      </div>
                    )}
                  </DataTableCell>
                  <DataTableCell>
                    <div
                      className="flex flex-col gap-1 w-[108px]"
                      title={
                        liqTotal > 0
                          ? `24h liq · long ${formatUsd(liqLong)} (${liqLongPct.toFixed(0)}%) / short ${formatUsd(liqShort)} (${liqShortPct.toFixed(0)}%)`
                          : "No liquidations in the last 24h"
                      }
                    >
                      {liqTotal > 0 ? (
                        <>
                          <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-bg-elevated">
                            <div
                              className="h-full bg-negative"
                              style={{ width: `${liqLongPct}%` }}
                            />
                            <div
                              className="h-full bg-positive"
                              style={{ width: `${liqShortPct}%` }}
                            />
                          </div>
                          <div className="flex items-baseline justify-between gap-1 text-[10px] leading-none">
                            <span className="text-negative tabular-nums">
                              L {formatUsd(liqLong)}
                            </span>
                            <span className="text-positive tabular-nums">
                              S {formatUsd(liqShort)}
                            </span>
                          </div>
                        </>
                      ) : (
                        <span className="text-[11px] text-text-dim">Quiet</span>
                      )}
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
                          {bias ?? "Mixed"}
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
        <div className="flex items-center justify-between mb-4 gap-4">
          <div>
            <h2 className="text-base font-semibold text-text-primary">
              Biggest Positions
            </h2>
            <p className="text-xs text-text-dim mt-1">
              Tracked whales only · ranked by open notional (not full-network)
            </p>
          </div>
          <p
            className="shrink-0 text-xs text-text-dim text-right"
            title={
              pipeline.last_collect_at
                ? `Whale book snapshot at ${pipeline.last_collect_at}`
                : undefined
            }
          >
            {pipeline.last_collect_at
              ? `As of ${formatTimeAgo(pipeline.last_collect_at)}`
              : "As of —"}
          </p>
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
                <p className="mb-1 font-medium text-text-primary">
                  Smart Money Score (out of 100)
                </p>
                <p>
                  Live: PnL 35% + ROI/momentum 30% + consistency 20% + swing adj
                  15%. Bar fill = score / 100. Hover ⓘ on Smart Money for the
                  full breakdown.
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
                  <ScoreMeter value={rank.smart_money_score} size="sm" />
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

      <div className="mt-2 mb-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-dim mb-3">
          Service health
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="rounded-xl border border-border bg-bg-surface p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Hyperliquid Market Status
            </h3>
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
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Pipeline Status
            </h3>
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
      </div>
    </DashboardLayout>
  );
}
