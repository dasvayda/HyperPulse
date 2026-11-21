import Link from "next/link";
import type { Metadata } from "next";
import { archivePage, getPublications, siteUrl, stanceLabel } from "@/lib/publications";

export const dynamic = "force-dynamic";

export async function generateMetadata({ searchParams }: { searchParams: Promise<{ page?: string }> }): Promise<Metadata> {
  const { page } = await searchParams;
  const origin = siteUrl();
  const current = archivePage(page);
  const path = `/briefs${current > 1 ? `?page=${current}` : ""}`;
  return { title: "Hyperliquid Market Briefs | HyperPulse", description: "Published Hyperliquid session analysis with tracked whale positioning, funding and changes since the previous session.",
    alternates: origin ? { canonical: `${origin}${path}` } : undefined };
}

export default async function BriefsPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const params = await searchParams;
  const page = archivePage(params.page);
  const archive = await getPublications(20, (page - 1) * 20);
  return <>
    <h1 className="text-3xl font-semibold tracking-tight">Hyperliquid market briefs</h1>
    <p className="mt-3 leading-relaxed text-text-muted">What changed in tracked whale positions, funding and the market since the previous session.</p>
    <div className="mt-8 space-y-5">
      {archive.items.length ? archive.items.map(item => <article key={item.slug} className="rounded-xl border border-border bg-bg-surface p-5">
        <p className="text-xs text-text-muted"><time dateTime={item.published_at}>{item.published_at.slice(0, 16).replace("T", " ")} UTC</time> · {item.label}</p>
        <h2 className="mt-2 text-xl font-semibold"><Link href={`/briefs/${item.slug}`} className="hover:text-accent">{item.title}</Link></h2>
        <p className="mt-3 leading-relaxed">{item.description || "Analysis unavailable in this archived edition."}</p>
        <span className="mt-3 inline-block text-sm text-accent">{stanceLabel(item.stance)}</span>
      </article>) : <p className="text-text-muted">No published briefs on this page. New editions appear during the Asia and US morning sessions when analysis is available.</p>}
    </div>
    <nav aria-label="Brief archive pages" className="mt-8 flex justify-between text-sm text-accent">
      {page > 1 ? <Link href={`/briefs?page=${page - 1}`}>← Newer briefs</Link> : <span />}
      {page * 20 < archive.total ? <Link href={`/briefs?page=${page + 1}`}>Older briefs →</Link> : null}
    </nav>
  </>;
}
