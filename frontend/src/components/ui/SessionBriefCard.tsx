import Link from "next/link";
import { getSessionBrief } from "@/lib/api";
import { describeSessionChange, sessionComparisonNote } from "@/lib/session-brief-copy";
import { EvidenceLink } from "./EvidenceLink";

export async function SessionBriefCard({ compact = false }: { compact?: boolean }) {
  const session = await getSessionBrief().catch(() => undefined);
  const note = session && sessionComparisonNote(session.status, session.changes.length > 0);
  return (
    <section id="session-brief" className="mb-4 min-w-0 break-words rounded-xl border border-border bg-bg-surface p-4">
      <h3 className="text-sm font-semibold text-text-primary">Session Brief</h3>
      {!session ? (
        <p className="mt-2 text-sm text-text-muted">{session === null
          ? "No session brief published yet. The live brief is shown separately."
          : "Session brief unavailable. Check the live brief separately."}</p>
      ) : (
        <>
          <p className="mt-1 text-xs text-text-muted">{session.slot_label} · Published {new Date(session.published_at).toISOString().slice(0, 16).replace("T", " ")} UTC</p>
          {session.baseline_label ? <p className="mt-1 text-xs text-text-muted">Compared with {session.baseline_label}{session.baseline_published_at ? ` · ${session.baseline_published_at.slice(0, 10)} UTC` : ""}</p> : null}
          {session.changes.length ? <ul className="mt-2 space-y-1 text-sm text-text-primary">
            {session.changes.map((change) => <li key={`${change.asset}:${change.metric}`}>{describeSessionChange(change)}</li>)}
          </ul> : null}
          {note ? <p className="mt-2 text-xs text-text-muted">{note}</p> : null}
          {session.read ? <p className="mt-3 text-sm text-text-primary">{session.read}</p> : null}
          <p className="mt-2 text-xs text-text-muted">Before acting, check the live price, funding and tracked whale positions for changes since publication.</p>
          <div className="mt-3 flex flex-wrap gap-3 text-xs">
            {compact ? <Link href="/insights#session-brief" className="text-accent hover:underline">Session details →</Link> : null}
            <EvidenceLink id={session.evidence_id} />
          </div>
        </>
      )}
    </section>
  );
}
