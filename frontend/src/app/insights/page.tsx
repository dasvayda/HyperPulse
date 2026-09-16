import Link from "next/link";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PageHeader } from "@/components/ui/DataTable";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { InsightCard } from "@/components/ui/InsightCard";
import { MarketBriefHero } from "@/components/ui/MarketBriefHero";
import { CohortHeatmap } from "@/components/ui/CohortHeatmap";
import { WhaleStyleTagsTable } from "@/components/ui/WhaleStyleTagsTable";
import {
  getAIInsights,
  getCohortHeatmap,
  getInferences,
  getMarketBrief,
  getPipelineStatus,
  formatTimeAgo,
} from "@/lib/api";

type InsightsPageProps = {
  searchParams: Promise<{ asset?: string }>;
};

export default async function InsightsPage({ searchParams }: InsightsPageProps) {
  const params = await searchParams;
  const asset = (params.asset || "").trim().toUpperCase() || undefined;
  const [insights, inferences, pipeline, brief, heatmap] = await Promise.all([
    getAIInsights(),
    getInferences(),
    getPipelineStatus(),
    getMarketBrief(asset),
    getCohortHeatmap(),
  ]);

  const tabs = brief.tab_assets?.length ? brief.tab_assets : [];
  const hasExtremeFunding = insights.some(
    (item) => item.title === "Extreme funding",
  );

  const ordered = [...insights].sort((a, b) => {
    const rank = (stance: string) =>
      stance === "buy" || stance === "sell" ? 0 : 1;
    return rank(a.stance) - rank(b.stance);
  });

  const chipClass = (active: boolean) =>
    `text-xs rounded-full border px-3 py-1.5 transition-colors ${
      active
        ? "border-accent text-accent bg-accent/10"
        : "border-border text-text-muted hover:border-accent/40 hover:text-text-primary"
    }`;

  return (
    <DashboardLayout>
      <PageHeader
        title="AI Insights"
        description="Desk brief from whale book + funding + liquidations — prefer long / short / wait"
      />

      <div className="flex flex-wrap gap-2 mb-4">
        <Link href="/insights#brief" className={chipClass(!asset)}>
          Market
        </Link>
        {tabs.map((tab) => (
          <Link
            key={tab}
            href={`/insights?asset=${encodeURIComponent(tab)}#brief`}
            className={chipClass(asset === tab)}
          >
            {tab}
          </Link>
        ))}
        {hasExtremeFunding ? (
          <Link href="/insights#evidence" className={chipClass(false)}>
            Extreme funding
          </Link>
        ) : null}
      </div>

      <MarketBriefHero brief={brief} />

      <div id="evidence" className="flex items-center justify-between mb-4 gap-3">
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

      <div className="mb-10">
        <CohortHeatmap data={heatmap} />
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
