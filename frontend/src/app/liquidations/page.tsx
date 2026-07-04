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
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { SparkBarBackground } from "@/components/ui/SparkBar";
import {
  getLiquidationZones,
  getLiquidationEvents,
  formatUsd,
  formatPrice,
  formatTimeAgo,
} from "@/lib/api";

export default async function LiquidationsPage() {
  const [zones, events] = await Promise.all([
    getLiquidationZones(),
    getLiquidationEvents(),
  ]);

  return (
    <DashboardLayout>
      <PageHeader
        title="Liquidation Radar"
        description="Monitor liquidation clusters and squeeze risk across Hyperliquid markets"
      />

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
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>
    </DashboardLayout>
  );
}
