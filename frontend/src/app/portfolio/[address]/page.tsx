import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  PageHeader,
  StatCard,
} from "@/components/ui/DataTable";
import { getTrader } from "@/lib/api";
import { formatUsd, formatPct } from "@/lib/api";

interface Props {
  params: Promise<{ address: string }>;
}

export default async function PortfolioPage({ params }: Props) {
  const { address } = await params;
  const trader = await getTrader(decodeURIComponent(address));

  return (
    <DashboardLayout>
      <PageHeader
        title={`Portfolio - ${trader.alias}`}
        description={trader.address}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total PnL"
          value={formatUsd(trader.pnl_usd)}
          change={formatPct(trader.pnl_change_pct)}
          positive={trader.pnl_change_pct >= 0}
        />
        <StatCard
          label="Win Rate"
          value={`${trader.win_rate}%`}
        />
        <StatCard
          label="Avg Hold Time"
          value={`${trader.avg_hold_hours}h`}
        />
        <StatCard
          label="Trades"
          value={trader.total_trades.toLocaleString()}
        />
      </div>
    </DashboardLayout>
  );
}

