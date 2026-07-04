import { Badge } from "@/components/ui/Badge";
import type { MarketInsight } from "@/types";
import { formatConfidence, formatTimeAgo } from "@/lib/api";

interface InsightCardProps {
  insight: MarketInsight;
}

export function InsightCard({ insight }: InsightCardProps) {
  return (
    <div className="rounded-xl border border-border bg-bg-surface p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{insight.title}</h3>
          {insight.asset && (
            <p className="text-xs text-text-muted mt-1">{insight.asset}</p>
          )}
        </div>
        <Badge variant="accent">{formatConfidence(insight.confidence)}</Badge>
      </div>
      <p className="text-sm text-text-muted leading-relaxed">{insight.summary}</p>
      <div className="flex flex-wrap gap-1.5">
        {insight.signals.map((signal) => (
          <Badge key={signal} variant="default">
            {signal}
          </Badge>
        ))}
      </div>
      <p className="text-xs text-text-dim">{formatTimeAgo(insight.created_at)}</p>
    </div>
  );
}
