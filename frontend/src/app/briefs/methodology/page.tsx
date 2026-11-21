import type { Metadata } from "next";
import { siteUrl } from "@/lib/publications";

export function generateMetadata(): Metadata {
  const origin = siteUrl();
  return { title: "HyperPulse analysis methods and coverage", description: "How HyperPulse builds and preserves Hyperliquid market briefs from tracked whale positions, funding and market snapshots.",
    alternates: origin ? { canonical: `${origin}/briefs/methodology` } : undefined };
}

export default function MethodologyPage() {
  return <article className="space-y-6 leading-relaxed">
    <h1 className="text-3xl font-semibold">How HyperPulse builds a market brief</h1>
    <p>HyperPulse publishes a view of Hyperliquid market conditions during the Asia and US morning sessions. Each edition preserves its analysis, observation time and comparison with the preceding published session.</p>
    <section><h2 className="text-xl font-semibold">Data and coverage</h2>
      <p className="mt-3">Inputs include market prices, hourly funding, tracked whale positions and available liquidation observations. The positioning sample covers the wallets tracked by HyperPulse. Individual editions show the coverage available at the observation time.</p>
      <p className="mt-3">Coverage describes how much of the tracked sample was available. Confidence on rule-based evidence cards describes agreement between rules. Neither figure measures a strategy’s win rate.</p>
      <a href="https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api" className="mt-3 inline-block text-accent hover:underline">Hyperliquid API documentation →</a>
    </section>
    <section><h2 className="text-xl font-semibold">Analysis and interpretation</h2>
      <p className="mt-3">The market-wide brief may use an AI model to summarise recorded inputs. When a model is unavailable, a rule-based summary may be used. Each edition identifies which method produced its analysis. Prefer longs, Prefer shorts and Wait express the stance of that edition.</p>
      <p className="mt-3">A large position’s average entry price describes the accumulated position. A verified fill price describes a confirmed trade. Changes between position snapshots can reflect several trades and need separate execution evidence.</p>
    </section>
    <section><h2 className="text-xl font-semibold">Publication and corrections</h2>
      <p className="mt-3">A session is published when usable analysis and recorded evidence are available. Stale, asset-specific and empty-coverage briefs are excluded from new session publication. An unavailable session can leave a gap in the archive.</p>
      <p className="mt-3">Reprocessing a published session preserves the original edition. Corrections and follow-up observations are appended with a date. Published editions can differ from the current live dashboard as markets move.</p>
    </section>
  </article>;
}
