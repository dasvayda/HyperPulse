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
  AssetIcon,
  TrendValue,
  StatCard,
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { SparkBarBackground } from "@/components/ui/SparkBar";
import {
  getLiquidationZones,
  getLiquidationEvents,
  getPipelineStatus,
  getMarketStatus,
  formatUsd,
  formatPrice,
  formatTimeAgo,
  getExplorerTxUrl,
} from "@/lib/api";

export default async function LiquidationsPage() {
  const [zones, events, pipeline, market] = await Promise.all([
    getLiquidationZones(),
    getLiquidationEvents(),
    getPipelineStatus(),
    getMarketStatus(),
  ]);

  const strip = [
    {
      label: "1h liquidations",
      total: market.liq_1h_total_usd ?? 0,
      long: market.liq_1h_long_usd ?? 0,
      short: market.liq_1h_short_usd ?? 0,
      pressure: market.liq_1h_pressure || "sampled liq quiet",
    },
    {
      label: "4h liquidations",
      total: market.liq_4h_total_usd ?? 0,
      long: market.liq_4h_long_usd ?? 0,
      short: market.liq_4h_short_usd ?? 0,
      pressure: market.liq_4h_pressure || "sampled liq quiet",
    },
    {
      label: "24h liquidations",
      total: market.liq_24h_total_usd ?? 0,
      long: market.liq_24h_long_usd ?? 0,
      short: market.liq_24h_short_usd ?? 0,
      pressure: market.liq_24h_pressure || "sampled liq quiet",
    },
  ];

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

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {strip.map((row) => (
          <StatCard
            key={row.label}
            label={row.label}
            value={formatUsd(row.total)}
            change={row.pressure}
            details={[
              {
                label: "Longs",
                value: formatUsd(row.long),
                tone: "negative",
              },
              {
                label: "Shorts",
                value: formatUsd(row.short),
                tone: "positive",
              },
            ]}
          />
        ))}
      </div>

      <h2 className="text-base font-semibold text-text-primary mb-4">
        Liquidation Zones
      </h2>
      <DataTable className="mb-10">
        <DataTableHead>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Price Level</DataTableHeaderCell>
          <DataTableHeaderCell>Distance</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>Liquidation Size</DataTableHeaderCell>
          <DataTableHeaderCell>OI Share</DataTableHeaderCell>
          <DataTableHeaderCell>Density</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {zones.map((zone) => (
            <DataTableRow key={zone.id}>
              <DataTableCell>
                <AssetIcon asset={zone.asset} />
              </DataTableCell>
              <DataTableCell className="font-medium">
                {formatPrice(zone.price, zone.asset)}
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
                <TrendValue
                  value={
                    zone.size_usd > 200_000_000
                      ? "High"
                      : zone.size_usd > 100_000_000
                        ? "Medium"
                        : "Low"
                  }
                />
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>

      <h2 className="text-base font-semibold text-text-primary mb-4">
        Recent Liquidation Events
      </h2>
      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>Asset</DataTableHeaderCell>
          <DataTableHeaderCell>Side</DataTableHeaderCell>
          <DataTableHeaderCell>Size</DataTableHeaderCell>
          <DataTableHeaderCell>Price</DataTableHeaderCell>
          <DataTableHeaderCell>Time</DataTableHeaderCell>
          <DataTableHeaderCell>Tx</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {events.map((event) => (
            <DataTableRow key={event.id}>
              <DataTableCell>
                <AssetIcon asset={event.asset} />
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
