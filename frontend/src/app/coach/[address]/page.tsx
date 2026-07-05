import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  PageHeader,
  StatCard,
} from "@/components/ui/DataTable";
import { getTrader } from "@/lib/api";
import { formatPct } from "@/lib/api";

interface Props {
  params: Promise<{ address: string }>;
}

export default async function CoachPage({ params }: Props) {
  const { address } = await params;
  const trader = await getTrader(decodeURIComponent(address));

  return (
    <DashboardLayout>
      <PageHeader
        title={`AI Coach - ${trader.alias}`}
        description="Strategy and risk summary based on live performance"
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="PnL Momentum"
          value={formatPct(trader.pnl_change_pct)}
          positive={trader.pnl_change_pct >= 0}
        />
        <StatCard
          label="Risk Score"
          value={`${trader.risk_score}/100`}
        />
        <StatCard
          label="Preferred Assets"
          value={trader.preferred_assets.join(", ") || "—"}
        />
        <StatCard
          label="Strategy Tags"
          value={trader.strategy_tags.join(", ") || "—"}
        />
      </div>
    </DashboardLayout>
  );
}

