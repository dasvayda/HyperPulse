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
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { InsightCard } from "@/components/ui/InsightCard";
import {
  getAIInsights,
  getInferences,
  getPipelineStatus,
  formatConfidence,
  formatTimeAgo,
} from "@/lib/api";

export default async function InsightsPage() {
  const [insights, inferences, pipeline] = await Promise.all([
    getAIInsights(),
    getInferences(),
    getPipelineStatus(),
  ]);

  const avgConfidence =
    inferences.length > 0
      ? inferences.reduce((sum, item) => sum + item.confidence, 0) / inferences.length
      : 0;

  return (
    <DashboardLayout>
      <PageHeader
        title="AI Strategy Inference"
        description="Strategy classification, risk profiles, and market commentary"
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Inferences"
          value={String(inferences.length)}
          change={`Provider: ${pipeline.ai_provider}`}
          positive
        />
        <StatCard
          label="Avg Confidence"
          value={formatConfidence(avgConfidence)}
          change="Across tracked whales"
          positive
        />
        <StatCard
          label="Market Insights"
          value={String(insights.length)}
          change="Live pipeline output"
          positive
        />
        <StatCard
          label="Last Run"
          value={
            pipeline.last_inference_at
              ? formatTimeAgo(pipeline.last_inference_at)
              : "—"
          }
          change="Inference cycle"
          positive
        />
      </div>

      <h2 className="text-base font-semibold text-text-primary mb-4">
        Market Insights
      </h2>
      <div className="mb-10 grid gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))]">
        {insights.map((insight) => (
          <InsightCard key={insight.id} insight={insight} />
        ))}
      </div>

      <h2 className="text-base font-semibold text-text-primary mb-4">
        Trader Strategy Classifications
      </h2>
      <DataTable>
        <DataTableHead>
          <DataTableHeaderCell>Trader</DataTableHeaderCell>
          <DataTableHeaderCell>Strategy</DataTableHeaderCell>
          <DataTableHeaderCell>Style</DataTableHeaderCell>
          <DataTableHeaderCell>Risk</DataTableHeaderCell>
          <DataTableHeaderCell>Confidence</DataTableHeaderCell>
          <DataTableHeaderCell>Provider</DataTableHeaderCell>
          <DataTableHeaderCell>Rationale</DataTableHeaderCell>
        </DataTableHead>
        <DataTableBody>
          {inferences.map((item) => (
            <DataTableRow key={item.id}>
              <DataTableCell>
                <Link
                  href={`/traders/${encodeURIComponent(item.trader_address)}`}
                  className="text-accent hover:underline font-medium"
                >
                  {item.trader_alias}
                </Link>
              </DataTableCell>
              <DataTableCell>
                <Badge variant="accent">{item.strategy}</Badge>
              </DataTableCell>
              <DataTableCell className="text-text-muted">
                {item.trading_style}
              </DataTableCell>
              <DataTableCell>
                <Badge
                  variant={
                    item.risk_profile === "Aggressive"
                      ? "short"
                      : item.risk_profile === "Conservative"
                        ? "long"
                        : "default"
                  }
                >
                  {item.risk_profile}
                </Badge>
              </DataTableCell>
              <DataTableCell>
                <div className="flex items-center gap-2">
                  <div className="w-12 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                    <div
                      className="h-full rounded-full bg-accent"
                      style={{ width: `${item.confidence}%` }}
                    />
                  </div>
                  <span className="text-xs text-text-muted">
                    {formatConfidence(item.confidence)}
                  </span>
                </div>
              </DataTableCell>
              <DataTableCell className="text-text-muted text-xs">
                {item.provider}
              </DataTableCell>
              <DataTableCell className="text-text-muted max-w-md whitespace-normal">
                {item.rationale}
              </DataTableCell>
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>
    </DashboardLayout>
  );
}
