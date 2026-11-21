import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiError } from "@/lib/api";
import { getPublication, siteUrl, socialDraft, stanceLabel } from "@/lib/publications";
import { describeSessionChange, sessionComparisonNote } from "@/lib/session-brief-copy";
import { CopySocialDraft } from "@/components/ui/CopySocialDraft";

export const dynamic = "force-dynamic";

async function load(slug: string) {
  try {
    return await getPublication(slug);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const article = await load(slug);
  const origin = siteUrl();
  const url = origin ? `${origin}/briefs/${article.slug}` : undefined;
  const title = `${article.title} | HyperPulse`;
  return { title, description: article.description,
    alternates: url ? { canonical: url } : undefined,
    openGraph: { type: "article", title, description: article.description, url,
      publishedTime: article.published_at, modifiedTime: article.modified_at, siteName: "HyperPulse",
      images: origin ? [`${origin}/briefs/opengraph-image`] : undefined },
    twitter: { card: "summary_large_image", title, description: article.description,
      images: origin ? [`${origin}/briefs/opengraph-image`] : undefined },
  };
}

export default async function BriefArticle({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = await load(slug);
  const origin = siteUrl();
  const digest = article.digest;
  const comparison = article.comparison;
  const comparisonNote = sessionComparisonNote(comparison.status, comparison.changes.length > 0);
  const context = digest?.as_of_line || article.tldr?.now;
  const caution = digest?.note || article.tldr?.however;
  const jsonLd = origin ? {
    "@context": "https://schema.org", "@type": "Article",
    headline: article.title, description: article.description, datePublished: article.published_at,
    dateModified: article.modified_at, mainEntityOfPage: `${origin}/briefs/${article.slug}`,
    author: { "@type": "Organization", name: "HyperPulse", url: `${origin}/briefs/methodology` },
    publisher: { "@type": "Organization", name: "HyperPulse", url: origin },
    image: `${origin}/briefs/opengraph-image`, inLanguage: "en",
  } : null;

  return <article>
    {jsonLd ? <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} /> : null}
    <p className="text-sm text-text-muted">{article.label} · Published <time dateTime={article.published_at}>{article.published_at.slice(0, 16).replace("T", " ")} UTC</time></p>
    <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{article.title}</h1>
    <p className="mt-4 text-sm text-text-muted">By HyperPulse · {article.source === "llm" ? "AI-generated analysis from recorded market inputs" : "Rule-based market summary"}</p>
    <span className="mt-4 inline-block rounded-lg border border-accent/30 px-3 py-1 text-sm text-accent">{stanceLabel(article.stance)}</span>
    <p className="mt-6 text-lg leading-relaxed">{article.description || "Analysis unavailable in this archived edition."}</p>
    <p className="mt-3 text-sm text-text-muted">Market observations as of <time dateTime={article.as_of}>{article.as_of.slice(0, 16).replace("T", " ")} UTC</time>. This edition preserves the view at publication.</p>

    <section className="mt-8 border-t border-border pt-6">
      <h2 className="text-lg font-semibold">Since the previous session</h2>
      {comparison.baseline_label ? <p className="mt-2 text-sm text-text-muted">Compared with {comparison.baseline_label}{comparison.baseline_published_at ? ` · ${comparison.baseline_published_at.slice(0, 16).replace("T", " ")} UTC` : ""}</p> : null}
      {comparison.changes.length ? <ul className="mt-3 space-y-2">{comparison.changes.map(change => <li key={`${change.asset}:${change.metric}`}>{describeSessionChange(change)}</li>)}</ul> : null}
      {comparisonNote ? <p className="mt-2 text-sm text-text-muted">{comparisonNote}</p> : null}
    </section>
    {context || digest?.funding_line ? <section className="mt-8">
      <h2 className="text-lg font-semibold">Market and funding</h2>
      {context ? <p className="mt-3 leading-relaxed">{context}</p> : null}
      {digest?.funding_line ? <p className="mt-2 leading-relaxed">{digest.funding_line}</p> : null}
    </section> : null}
    {digest?.positioning.length ? <section className="mt-8">
      <h2 className="text-lg font-semibold">Tracked whale positions</h2>
      <ul className="mt-3 space-y-2">{digest.positioning.map((line, index) => <li key={index} className="leading-relaxed">{line}</li>)}</ul>
    </section> : null}
    {caution || article.risks.length ? <section className="mt-8 rounded-xl border border-border bg-bg-surface p-5">
      <h2 className="text-lg font-semibold">Before acting</h2>
      {caution ? <p className="mt-3 leading-relaxed">{caution}</p> : null}
      <ul className="mt-3 space-y-2 text-text-muted">{article.risks.filter(risk => risk !== caution).map((risk, index) => <li key={index}>{risk}</li>)}</ul>
    </section> : null}
    {article.suggestions.length ? <details className="mt-6 rounded-xl border border-border p-5">
      <summary className="cursor-pointer">What this implies</summary>
      <ul className="mt-3 space-y-2">{article.suggestions.map((line, index) => <li key={index}>{line}</li>)}</ul>
    </details> : null}
    {article.notes.length ? <section className="mt-8 border-t border-border pt-6">
      <h2 className="text-lg font-semibold">Corrections and follow-up</h2>
      {article.notes.map(note => <div key={note.id} className="mt-4">
        <p className="text-sm text-text-muted">{note.kind === "correction" ? "Correction" : "Follow-up"} · <time dateTime={note.created_at}>{note.created_at.slice(0, 16).replace("T", " ")} UTC</time></p>
        <p className="mt-2 whitespace-pre-line leading-relaxed">{note.text}</p>
      </div>)}
    </section> : null}
    <section className="mt-8 border-t border-border pt-6 text-sm leading-relaxed text-text-muted">
      <p>Positioning describes our tracked wallet sample. Coverage and snapshot timing affect the analysis. Check current prices and positions before trading.</p>
      <p className="mt-3">Source data comes from Hyperliquid market and account snapshots. Funding refers to the hourly rate. Position snapshot changes alone do not confirm executed trades.</p>
      <Link href="/briefs/methodology" className="mt-3 inline-block text-accent hover:underline">Analysis methods and data coverage →</Link>
      <Link href={`/evidence/${article.evidence_id}`} className="mt-3 block text-accent hover:underline">Recorded inputs (beta access) →</Link>
    </section>
    <div className="mt-8 flex flex-wrap gap-5 text-sm text-accent">
      <Link href="/insights">Check live insights →</Link>
      <Link href="/briefs">Read another session →</Link>
      <Link href="/alerts">View Telegram subscription options →</Link>
    </div>
    {origin ? <CopySocialDraft text={socialDraft(article, origin)} /> : null}
  </article>;
}
