import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PageHeader } from "@/components/ui/DataTable";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { InsightCard } from "@/components/ui/InsightCard";
import { MarketBriefHero } from "@/components/ui/MarketBriefHero";
import { WhaleStyleTagsTable } from "@/components/ui/WhaleStyleTagsTable";
import {
  getAIInsights,
  getInferences,
  getMarketBrief,
  getPipelineStatus,
  formatTimeAgo,
} from "@/lib/api";

export default async function InsightsPage() {
  const [insights, inferences, pipeline, brief] = await Promise.all([
    getAIInsights(),
    getInferences(),
    getPipelineStatus(),
    getMarketBrief(),
  ]);

  const ordered = [...insights].sort((a, b) => {
    const rank = (stance: string) =>
      stance === "buy" || stance === "sell" ? 0 : 1;
    return rank(a.stance) - rank(b.stance);
  });

  return (
    <DashboardLayout>
      <PageHeader
        title="AI Insights"
        description="Desk brief from whale book + funding + liquidations — prefer long / short / wait"
      />

      <MarketBriefHero brief={brief} />

      <div className="flex items-center justify-between mb-4 gap-3">
        <h2 className="text-base font-semibold text-text-primary">Evidence</h2>
        <InfoTooltip label="Rule cards">
          <p className="mb-1 font-medium text-text-primary">
            Prefer long / short evidence
          </p>
          <p>
            These cards are built from Hyperliquid whale book, funding, and
            liquidation rules — not the LLM brief. Confidence is vote strength,
            not win rate.
          </p>
        </InfoTooltip>
      </div>
      <div className="mb-10 grid gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))]">
        {ordered.length > 0 ? (
          ordered.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))
        ) : (
          <p className="text-sm text-text-muted">
            No evidence cards yet — wait for the next inference cycle.
          </p>
        )}
      </div>

      <WhaleStyleTagsTable
        inferences={inferences}
        providerLabel={pipeline.ai_provider}
        lastRunLabel={
          pipeline.last_inference_at
            ? formatTimeAgo(pipeline.last_inference_at)
            : "—"
        }
      />
    </DashboardLayout>
  );
}
