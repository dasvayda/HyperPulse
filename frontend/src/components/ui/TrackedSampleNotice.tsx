import { Info } from "lucide-react";

export function TrackedSampleNotice({ tracked }: { tracked?: number }) {
  return (
    <section className="mb-5 flex gap-3 rounded-xl border border-border bg-bg-surface px-4 py-3 text-sm text-text-muted">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
      <p>
        Built from a tracked Hyperliquid whale sample{tracked ? ` (${tracked} wallets)` : ""},
        not every account on the exchange. Use this as a signal to check before
        entering a trade, not proof of the whole market.
      </p>
    </section>
  );
}
