import { Badge } from "@/components/ui/Badge";
import { PulseBar, pulseChipLabel } from "@/components/ui/PulseBar";
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
  const tldr = brief.tldr;
  const pulse = brief.pulse;
  return (
    <section
      id="brief"
      className="rounded-xl border border-border bg-bg-surface p-6 mb-8"
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-text-dim mb-2">
            Market Brief
            {brief.asset ? ` · ${brief.asset}` : ""}
          </p>
          <h2 className="text-xl font-semibold text-text-primary leading-snug">
            {brief.headline}
          </h2>
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {brief.stale ? (
            <Badge variant="exit" className="text-xs font-semibold px-2.5 py-1">
              STALE
            </Badge>
          ) : null}
          <Badge
            variant={stanceVariant[brief.stance]}
            className="text-xs font-semibold tracking-wide px-2.5 py-1"
          >
            {stanceLabel[brief.stance]}
          </Badge>
          {pulse ? (
            <Badge
              variant="default"
              className="text-xs font-semibold tracking-wide px-2.5 py-1"
              title="15m direction probability from whale/funding/liq rules"
            >
              {pulseChipLabel(pulse)}
            </Badge>
          ) : null}
        </div>
      </div>

      {pulse ? (
        <div className="mt-3 max-w-sm">
          <PulseBar pulse={pulse} compact />
        </div>
      ) : null}

      {tldr ? (
        <ul className="mt-4 space-y-2">
          <li className="text-sm text-text-primary leading-relaxed pl-3 border-l border-accent/50">
            {tldr.now}
          </li>
          <li className="text-sm text-text-muted leading-relaxed pl-3 border-l border-border">
            {tldr.short_read}
          </li>
          <li className="text-sm text-text-muted leading-relaxed pl-3 border-l border-border">
            {tldr.however}
          </li>
        </ul>
      ) : null}

      <details className="mt-4 group">
        <summary className="text-xs font-medium text-text-dim cursor-pointer list-none">
          Current state
        </summary>
        <p className="mt-2 text-sm text-text-muted leading-relaxed">
          {brief.market_status}
        </p>
      </details>

      {(brief.suggestions.length > 0 || brief.risks.length > 0) && (
        <details className="mt-3 group">
          <summary className="text-xs font-medium text-text-dim cursor-pointer list-none">
            What this implies
          </summary>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
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
        </details>
      )}

      <p className="mt-5 text-xs text-text-dim">
        Tracked whale book + funding + sampled liq ·{" "}
        {formatTimeAgo(brief.as_of)} · {brief.source}/{brief.provider}
        {brief.evidence_refs.length > 0
          ? ` · refs: ${brief.evidence_refs.join(", ")}`
          : ""}
      </p>
    </section>
  );
}
