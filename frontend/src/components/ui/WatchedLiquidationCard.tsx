import Link from "next/link";
import { StatCard } from "./DataTable";
import { formatUsd } from "@/lib/api";
import { sampleAmounts, type WatchedLiquidations } from "@/lib/liquidation-sample";

export function WatchedLiquidationCard({ sample, window }: {
  sample: WatchedLiquidations | null; window: "1h" | "4h" | "24h";
}) {
  const amounts = sampleAmounts(sample?.windows[window]);
  return <Link href="/liquidations#watched-liquidations" className="block rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
    <StatCard label={`Watched liquidations · ${window}`}
      value={amounts.available ? formatUsd(amounts.long + amounts.short) : "Unavailable"}
      change={`${sample?.wallets.length ?? 0} wallets · ${amounts.complete ? "Full sample window" : amounts.available ? "Observed only · partial coverage" : "Feed offline / not ready"}`}
      details={amounts.available ? [
        { label: "Longs", value: formatUsd(amounts.long), tone: "negative" },
        { label: "Shorts", value: formatUsd(amounts.short), tone: "positive" },
      ] : []} />
  </Link>;
}
