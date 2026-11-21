import Link from "next/link";
import type { Metadata } from "next";
import { siteUrl } from "@/lib/publications";

export function generateMetadata(): Metadata {
  const origin = siteUrl();
  return { metadataBase: origin ? new URL(origin) : undefined };
}

export default function BriefsLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-bg-primary text-text-primary">
    <header className="border-b border-border">
      <nav aria-label="Public navigation" className="mx-auto flex max-w-3xl flex-wrap items-center gap-x-6 gap-y-3 px-5 py-5">
        <Link href="/briefs" className="mr-auto text-lg font-semibold">HyperPulse</Link>
        <Link href="/briefs" className="text-sm text-accent">Market briefs</Link>
        <Link href="/briefs/methodology" className="text-sm text-text-muted">How we analyse</Link>
        <Link href="/insights" className="text-sm text-accent">Live insights →</Link>
      </nav>
    </header>
    <main className="mx-auto max-w-3xl px-5 py-10 sm:py-14">{children}</main>
    <footer className="mx-auto max-w-3xl border-t border-border px-5 py-6 text-sm text-text-muted">
      HyperPulse · Hyperliquid intelligence from a tracked wallet sample.
    </footer>
  </div>;
}
