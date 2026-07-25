import { Badge } from "@/components/ui/Badge";
import type { MarketBrief } from "@/types";
import { formatTimeAgo } from "@/lib/api";

interface MarketBriefHeroProps {
  brief: MarketBrief;
}

const stanceLabel: Record<MarketBrief["stance"], string> = {
  prefer_long: "Prefer longs",
  prefer_short: "Prefer shorts",
  wait: "Wait",
};

const stanceVariant: Record<
  MarketBrief["stance"],
  "buy" | "sell" | "hold"
> = {
  prefer_long: "buy",
  prefer_short: "sell",
  wait: "hold",
};

export function MarketBriefHero({ brief }: MarketBriefHeroProps) {
  return (
    <section className="rounded-xl border border-border bg-bg-surface p-6 mb-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-text-dim mb-2">
            Market Brief
          </p>
          <h2 className="text-xl font-semibold text-text-primary leading-snug">
            {brief.headline}
          </h2>
        </div>
        <Badge
          variant={stanceVariant[brief.stance]}
          className="text-xs font-semibold tracking-wide px-2.5 py-1 shrink-0"
        >
          {stanceLabel[brief.stance]}
        </Badge>
      </div>

      <p className="mt-4 text-sm text-text-muted leading-relaxed">
        {brief.market_status}
      </p>

      {(brief.suggestions.length > 0 || brief.risks.length > 0) && (
        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          {brief.suggestions.length > 0 && (
            <div>
              <p className="text-xs font-medium text-text-primary mb-2">
                Suggestions
              </p>
              <ul className="space-y-1.5">
                {brief.suggestions.map((item) => (
                  <li
                    key={item}
                    className="text-sm text-text-muted leading-relaxed pl-3 border-l border-accent/40"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {brief.risks.length > 0 && (
            <div>
              <p className="text-xs font-medium text-text-primary mb-2">Risks</p>
              <ul className="space-y-1.5">
                {brief.risks.map((item) => (
                  <li
                    key={item}
                    className="text-sm text-text-muted leading-relaxed pl-3 border-l border-border"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <p className="mt-5 text-xs text-text-dim">
        Based on live whale / funding / liq snapshot ·{" "}
        {formatTimeAgo(brief.as_of)} · {brief.source}/{brief.provider}
        {brief.evidence_refs.length > 0
          ? ` · refs: ${brief.evidence_refs.join(", ")}`
          : ""}
      </p>
    </section>
  );
}
