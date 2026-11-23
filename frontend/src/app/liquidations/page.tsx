import Link from "next/link";
import { WatchedLiquidationCard } from "@/components/ui/WatchedLiquidationCard";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeaderCell,
  DataTableRow,
  PageHeader,
  AssetIcon,
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { SparkBarBackground } from "@/components/ui/SparkBar";
import {
  getLiquidationZones,
  getLiquidationEvents,
  getPipelineStatus,
  getLiqProximity,
  getWatchedLiquidationWindows,
  formatUsd,
  formatPrice,
  formatTimeAgo,
  getExplorerTxUrl,
} from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function LiquidationsPage() {
  const [zones, legacyEvents, pipeline, proximity, verified] = await Promise.all([
    getLiquidationZones(),
    getLiquidationEvents(),
    getPipelineStatus(),
    getLiqProximity(8),
    getWatchedLiquidationWindows().catch(() => null),
  ]);

  const events = pipeline.data_source === "mock" ? legacyEvents.map(event => ({ ...event, wallet: null })) : (verified?.recent_events ?? []).map(event => ({
    ...event, timestamp: event.event_at,
  }));

  return (
    <DashboardLayout>
      <PageHeader
        title="Liquidation Radar"
        description="Monitor liquidation clusters and squeeze risk across Hyperliquid markets"
        actions={
          <span className="text-xs text-text-dim border border-border rounded-full px-3 py-1">
            Data source: {pipeline.data_source}
          </span>
        }
      />

      <section id="watched-liquidations" className="mb-5 scroll-mt-6 rounded-xl border border-border bg-bg-surface p-4 text-sm text-text-muted">
        <h2 className="text-text-primary">Watched wallet liquidations</h2>
        <p>{verified?.wallets.length ?? 0} fixed wallets · actual liquidation fills from Hyperliquid.</p>
        <p>This sample does not measure market-wide liquidations. Partial windows show only observed fills; missing coverage is not zero activity.</p>
        <p>Coverage restarts after a disconnect or roster change. A full 24h window needs 24 uninterrupted hours.</p>
      </section>

      <details className="mb-5 rounded-xl border border-border bg-bg-surface p-4 text-sm text-text-muted">
        <summary className="cursor-pointer text-text-primary">Where these risk levels come from</summary>
        <div className="mt-3 space-y-2">
          <p>Closest Tracked Whales uses each wallet&apos;s open positions. Actual liquidation prices come from Hyperliquid account state; rows marked estimate use a model. Distance compares that price with the market mark.</p>
          <p>LIQ WATCH and DANGER alerts use actual liquidation prices only. Open a trader to check their positions. Zones group qualifying tracked positions into 1% price bands within 50% of the mark. Each band separates Hyperliquid liquidation prices from estimates; the displayed price is weighted by position size. They are risk levels, not executed liquidations.</p>
          <p>Estimates use position entry and leverage; cross-margin collateral and other positions can change the actual liquidation price. Stale observations and estimates already behind the mark are excluded. LIQ WATCH alerts never use these estimates.</p>
        </div>
      </details>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {(["1h", "4h", "24h"] as const).map(window => (
          <WatchedLiquidationCard key={window} sample={verified} window={window} />
        ))}
      </div>

      <div id="tracked-whale-risk" className="mb-10 scroll-mt-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-text-primary">
              Closest Tracked Whales
            </h2>
            <p className="text-xs text-text-dim mt-1">
              Distance to liquidationPx (or estimate) · lower % = closer risk
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
            <DataTableHeaderCell>Distance</DataTableHeaderCell>
            <DataTableHeaderCell>Liq / Mark</DataTableHeaderCell>
          </DataTableHead>
          <DataTableBody>
            {proximity.length > 0 ? (
              proximity.map((row) => (
                <DataTableRow
                  key={`${row.trader_address}-${row.asset}-${row.side}-${row.rank}`}
                >
                  <DataTableCell className="text-text-muted font-mono">
                    {row.rank}
                  </DataTableCell>
                  <DataTableCell>
                    <Link
                      href={`/traders/${encodeURIComponent(row.trader_address)}`}
                      className="text-sm text-accent hover:underline"
                    >
                      {row.trader_alias}
                    </Link>
                  </DataTableCell>
                  <DataTableCell>
                    <AssetIcon asset={row.asset} />
                  </DataTableCell>
                  <DataTableCell>
                    <Badge variant={row.side}>{row.side.toUpperCase()}</Badge>
                  </DataTableCell>
                  <DataTableCell className="text-sm text-text-primary">
                    {formatUsd(row.size_usd)}
                    <span className="block text-[11px] text-text-dim">
                      {row.leverage.toFixed(1)}x
                    </span>
                  </DataTableCell>
                  <DataTableCell>
                    <span
                      className={`text-sm font-medium ${
                        row.distance_pct <= 5
                          ? "text-negative"
                          : row.distance_pct <= 12
                            ? "text-text-primary"
                            : "text-text-muted"
                      }`}
                    >
                      {row.distance_pct.toFixed(1)}%
                    </span>
                    {row.source === "estimate" && (
                      <span className="block text-[10px] text-text-dim">
                        estimate
                      </span>
                    )}
                  </DataTableCell>
                  <DataTableCell className="text-xs text-text-muted">
                    {formatPrice(row.liquidation_px, row.asset)}
                    <span className="block text-text-dim">
                      mark {formatPrice(row.mark_price, row.asset)}
                    </span>
                  </DataTableCell>
                </DataTableRow>
              ))
            ) : (
              <DataTableRow>
                <DataTableCell className="text-text-dim">
                  No proximity rows yet — needs live whale book + marks.
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

      <h2 className="text-base font-semibold text-text-primary mb-4">
        Tracked Liquidation Zones
      </h2>
      <p className="mb-4 text-xs text-text-muted">Zones use all qualifying tracked positions. The liquidation fill feed above watches only its fixed wallet sample.</p>
      <DataTable className="mb-10">
        <DataTableHead>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Price Level</DataTableHeaderCell>
          <DataTableHeaderCell>Distance</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>Position Size at Risk</DataTableHeaderCell>
          <DataTableHeaderCell>OI Share</DataTableHeaderCell>
          <DataTableHeaderCell>Sample</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {zones.length === 0 ? <DataTableRow>
            <td colSpan={7} className="px-4 py-5 text-sm text-text-muted">
              Liquidation zone data is unavailable. Check Closest Tracked Whales above for position-level risk.
            </td>
          </DataTableRow> : null}
          {zones.map((zone) => (
            <DataTableRow key={zone.id}>
              <DataTableCell>
                <AssetIcon asset={zone.asset} />
              </DataTableCell>
              <DataTableCell className="font-medium">
                {formatPrice(zone.price, zone.asset)}
                <span className="block text-[11px] text-text-dim">{zone.source === "liquidationPx" ? "Hyperliquid liq price" : "Estimate · entry/leverage"}</span>
                {zone.observed_at ? <span className="block text-[11px] text-text-dim">Updated {formatTimeAgo(zone.observed_at)}</span> : null}
              </DataTableCell>
              <DataTableCell>
                <span
                  className={
                    zone.distance_pct >= 0
                      ? "text-positive text-sm font-medium"
                      : "text-negative text-sm font-medium"
                  }
                >
                  {zone.distance_pct >= 0 ? "↑" : "↓"}{" "}
                  {Math.abs(zone.distance_pct).toFixed(1)}%
                </span>
              </DataTableCell>
              <DataTableCell>
                <Badge variant={zone.side}>
                  {zone.side === "long" ? "LONG LIQ" : "SHORT LIQ"}
                </Badge>
              </DataTableCell>
              <DataTableCell>
                <SparkBarBackground
                  values={zone.sparkline}
                  color={zone.side === "long" ? "negative" : "positive"}
                >
                  <span className="font-medium text-text-primary">
                    {formatUsd(zone.size_usd)}
                  </span>
                </SparkBarBackground>
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {zone.open_interest_pct}%
              </DataTableCell>
              <DataTableCell>
                <span className="text-xs text-text-muted">{zone.positions ?? 0} positions · {zone.wallets ?? 0} wallets</span>
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <h2 className="text-base font-semibold text-text-primary mb-4">
        Recent Watched Liquidations · 24h
      </h2>
      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Wallet</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>Size</DataTableHeaderCell>
          <DataTableHeaderCell>Price</DataTableHeaderCell>
          <DataTableHeaderCell>Time</DataTableHeaderCell>
          <DataTableHeaderCell>Tx</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {events.length === 0 ? <DataTableRow>
            <td colSpan={7} className="px-4 py-5 text-sm text-text-muted">
              {!verified || verified.windows["24h"].status === "unavailable" ? "Liquidation feed is offline or not ready. Missing data is not zero activity." : "No verified liquidations observed in these wallets. Partial coverage may miss events."}
            </td>
          </DataTableRow> : null}
          {events.map((event) => (
            <DataTableRow key={event.id}>
              <DataTableCell>
                <AssetIcon asset={event.asset} />
              </DataTableCell>
              <DataTableCell>
                {event.wallet ? <Link href={`/traders/${event.wallet}`} className="font-mono text-xs text-accent hover:underline" title={event.wallet}>{event.wallet.slice(0, 6)}…{event.wallet.slice(-4)}</Link> : "—"}
              </DataTableCell>
              <DataTableCell>
                <Badge variant={event.side}>
                  {event.side.toUpperCase()}
                </Badge>
              </DataTableCell>
              <DataTableCell className="font-medium">
                {formatUsd(event.size_usd)}
              </DataTableCell>
              <DataTableCell>
                {formatPrice(event.price, event.asset)}
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {formatTimeAgo(event.timestamp)}
              </DataTableCell>
              <DataTableCell>
                {event.tx_hash ? (
                  <Link
                    href={getExplorerTxUrl(event.tx_hash)}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono text-xs text-accent hover:underline"
                    title={event.tx_hash}
                  >
                    {`${event.tx_hash.slice(0, 8)}...${event.tx_hash.slice(-6)}`}
                  </Link>
                ) : (
                  <span className="text-xs text-text-dim">—</span>
                )}
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>
    </DashboardLayout>
  );
}
