import Link from "next/link";
import { cookies } from "next/headers";
import { timingSafeEqual } from "node:crypto";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PageHeader } from "@/components/ui/DataTable";

export const dynamic = "force-dynamic";

type Evidence = {
  kind: string; created_at: string;
  inputs: Record<string, unknown>;
  context: {
    scope: string; rank_policy: string;
    rankings: { address: string; rank: number; smart_money_rank: number | null; smart_money_score: number }[];
    size_ranks: { address: string; size_rank: number }[];
    positions: { trader_address: string; asset: string; side: string; size_usd: number }[];
    market: Record<string, unknown>; collectors: Record<string, unknown>;
    flows: { wallet: string; asset: string; previous_usd: number; current_usd: number; delta_usd: number; as_of: string }[];
    liquidation_coverage: { status: string; scope: string; gap: boolean };
  };
};

export default async function EvidencePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let evidence: Evidence | null = null;
  if (/^[0-9a-f]{64}$/.test(id)) {
    try {
      const base = process.env.API_URL ?? "http://127.0.0.1:8100";
      const token = process.env.EVIDENCE_ACCESS_TOKEN;
      const presented = (await cookies()).get("evidence_access")?.value ?? "";
      const authorized = token && Buffer.byteLength(token) === Buffer.byteLength(presented) &&
        timingSafeEqual(Buffer.from(token), Buffer.from(presented));
      if (token && !authorized) throw new Error("Evidence access required");
      const response = await fetch(`${base}/api/v2/evidence/${id}`, {
        cache: "no-store", signal: AbortSignal.timeout(10_000),
        headers: token ? { "X-Evidence-Token": token } : {},
      });
      if (response.ok) evidence = await response.json();
    } catch { /* The page keeps unavailable evidence explicit. */ }
  }
  const context = evidence?.context;
  return <DashboardLayout>
    <PageHeader title="Signal evidence" description="Saved inputs at the time of this read. Current rankings may differ." />
    {!evidence || !context ? <p className="text-text-muted">Evidence unavailable or access is restricted. No current data has been substituted.</p> :
      <section className="space-y-5 rounded-xl border border-border bg-bg-surface p-5 text-sm text-text-muted break-words">
        <p>Saved {evidence.created_at} · {evidence.kind} · Tracked wallet sample</p>
        <p>Liquidations: {context.liquidation_coverage.status} · {context.liquidation_coverage.scope} · {context.liquidation_coverage.gap ? "Coverage has gaps" : "Observed window complete"}. Market-wide coverage unavailable.</p>
        <p>Size rank compares tracked account sizes. Smart Money rank compares scores within the size-selected cohort. Neither is a rating of this trade.</p>
        <details open><summary className="cursor-pointer text-text-primary">Wallets and positions at signal time</summary>
          <div className="mt-3 space-y-3">{context.positions.map((position, index) => {
            const ranking = context.rankings.find(r => r.address.toLowerCase() === position.trader_address.toLowerCase());
            const size = context.size_ranks.find(r => r.address.toLowerCase() === position.trader_address.toLowerCase());
            return <p key={index}><Link className="text-accent" href={`/traders/${position.trader_address}`}>{position.trader_address}</Link><br />
              {position.asset} · {position.side} · ${position.size_usd.toLocaleString()} · Size #{size?.size_rank ?? "unavailable"} · Smart Money #{ranking?.smart_money_rank ?? "outside cohort"} · Score {ranking?.smart_money_score ?? "unavailable"}</p>;
          })}{!context.positions.length && <p>No wallet positions recorded in this snapshot.</p>}</div>
        </details>
        <details><summary className="cursor-pointer text-text-primary">Position changes (snapshot changes, not verified fills)</summary>
          <div className="mt-3 space-y-2">{context.flows.map((flow, i) => <p key={i}>{flow.wallet} · {flow.asset} · ${flow.previous_usd} → ${flow.current_usd} · delta ${flow.delta_usd} · {flow.as_of}</p>)}
          {!context.flows.length && <p>No recent position changes recorded.</p>}</div>
        </details>
        <details><summary className="cursor-pointer text-text-primary">Market inputs and source times</summary>
          <pre className="mt-3 whitespace-pre-wrap break-all text-xs">{JSON.stringify({ inputs: evidence.inputs, market: context.market, sources: context.collectors }, null, 2)}</pre>
        </details>
      </section>}
  </DashboardLayout>;
}
