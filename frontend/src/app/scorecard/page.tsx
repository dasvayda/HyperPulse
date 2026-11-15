import Link from "next/link";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { PageHeader } from "@/components/ui/DataTable";
import { EvidenceLink } from "@/components/ui/EvidenceLink";
import { BetaVisit } from "@/components/ui/BetaVisit";
import { getPulseScorecard } from "@/lib/api";

export const dynamic = "force-dynamic";
const labels = { hit: "Matched", miss: "Missed", wait: "Wait", pending: "Pending", unavailable: "No observation" };

export default async function ScorecardPage({ searchParams }: {
  searchParams: Promise<{ asset?: string; days?: string; offset?: string; day?: string }>;
}) {
  const params = await searchParams;
  const asset = typeof params.asset === "string" ? params.asset.slice(0, 32).trim().toUpperCase() : "";
  const days = params.days === "1" ? 1 : params.days === "30" ? 30 : 7;
  const offset = Math.min(100000, Math.max(0, Math.floor(Number(params.offset) || 0)));
  const day = typeof params.day === "string" && /^\d{4}-\d{2}-\d{2}$/.test(params.day) ? params.day : "";
  const data = await getPulseScorecard(asset, days, offset, day).catch(() => null);
  const page = (start: number) => `/scorecard?${new URLSearchParams({ asset, days: String(days), offset: String(start), ...(day ? {day} : {}) })}`;
  return <DashboardLayout>
    <PageHeader title="15m Signal Scorecard" description="What the signal said, and what the mark price did next. Not a trade or a return." />
    <form action="/scorecard" className="mb-4 flex flex-wrap items-end gap-3 text-sm">
      <label>Asset <input name="asset" maxLength={32} defaultValue={asset} placeholder="All assets" className="block w-32 rounded border border-border bg-bg-surface p-2" /></label>
      <label>Date (UTC) <input type="date" name="day" defaultValue={day} className="block rounded border border-border bg-bg-surface p-2" /></label>
      <label>Window <select name="days" defaultValue={days} className="block rounded border border-border bg-bg-surface p-2">
        <option value="1">24 hours</option><option value="7">7 days</option><option value="30">30 days</option>
      </select></label>
      <button className="rounded border border-border px-3 py-2 text-accent">Apply</button>
    </form>
    {!data ? <p>Scorecard unavailable. Try again later.</p> : <>
      <p className="mb-2 text-sm text-text-muted">{day ? `${day} UTC` : `Last ${days}d`} · {data.total} signals · {data.directional_evaluated} evaluated directional calls · {data.engine}</p>
      <p className="mb-4 flex flex-wrap gap-3 text-sm">{Object.entries(labels).map(([key, label]) =>
        <span key={key}>{label}: {data.counts[key as keyof typeof labels]}</span>)}</p>
      {!data.items.length ? <p className="text-text-muted">{data.total ? "No signals on this page." : "No eligible signals in this window yet. Older records are not backfilled."}</p> :
        <ul className="space-y-3">{data.items.map(item => <li key={item.id} className="break-words rounded-xl border border-border bg-bg-surface p-4 text-sm">
          <p className="font-medium">{item.asset} · {item.direction.toUpperCase()} · {labels[item.status]}</p>
          <p className="mt-1 text-text-muted">Signal: {item.as_of} · Mark {item.baseline_mark}</p>
          <p className="text-text-muted">15m target: {item.due_at}</p>
          {item.observed_at ? <p className="text-text-muted">Observed: {item.observed_at} · Mark {item.result_mark}</p> : null}
          <EvidenceLink id={item.evidence_id} />
        </li>)}</ul>}
      <div className="mt-4 flex gap-4 text-sm text-accent">
        {offset > 0 ? <Link href={page(Math.max(0, offset - 25))}>Previous</Link> : null}
        {offset + 25 < data.total ? <Link href={page(offset + 25)}>Next</Link> : null}
      </div>
    </>}
    <p className="mt-5 text-xs text-text-muted">A selected UTC date overrides the rolling window. These are independent Pulse signals, not results of a whale trade or session brief. Uses the first observed mark from +15m to +17m. Moves under 5 bps count as flat; Wait is separate from directional results. No fees or fills are modeled.</p>
    {data && process.env.BETA_METRICS_ENABLED === "true" ? <BetaVisit event="scorecard_view" /> : null}
  </DashboardLayout>;
}
