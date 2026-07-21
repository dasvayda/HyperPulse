import { Badge } from "@/components/ui/Badge";
import type { InsightStance, MarketInsight } from "@/types";
import { formatConfidence, formatTimeAgo } from "@/lib/api";

interface InsightCardProps {
  insight: MarketInsight;
  className?: string;
}

const stanceVariant: Record<InsightStance, "buy" | "sell" | "hold"> = {
  buy: "buy",
  sell: "sell",
  hold: "hold",
};

export function InsightCard({ insight, className = "" }: InsightCardProps) {
  const stance = insight.stance ?? "hold";

  return (
    <div
      className={`rounded-xl border border-border bg-bg-surface p-6 flex flex-col gap-3.5 w-full min-h-[200px] ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={stanceVariant[stance]} className="text-xs font-semibold tracking-wide px-2.5 py-1">
              {stance.toUpperCase()}
            </Badge>
            {insight.asset && (
              <span className="text-xs text-text-muted">{insight.asset}</span>
            )}
          </div>
          <h3 className="text-base font-semibold text-text-primary mt-2.5">{insight.title}</h3>
        </div>
        <Badge variant="accent">{formatConfidence(insight.confidence)}</Badge>
      </div>
      <p className="text-sm text-text-muted leading-relaxed flex-1">{insight.summary}</p>
      <div className="flex flex-wrap gap-1.5">
        {insight.signals
          .filter((signal) => !signal.toLowerCase().startsWith("action:"))
          .map((signal) => (
            <Badge key={signal} variant="default">
              {signal}
            </Badge>
          ))}
      </div>
      <p className="text-xs text-text-dim">{formatTimeAgo(insight.created_at)}</p>
    </div>
  );
}
