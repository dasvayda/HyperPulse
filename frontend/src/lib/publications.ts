import { cache } from "react";
import { fetchApi } from "./api";
import type { MarketBrief, SessionBrief } from "../types";

export type PublicationSummary = {
  slug: string; slot_id: string; label: string; title: string; description: string;
  published_at: string; as_of: string; stance: MarketBrief["stance"]; source: string; modified_at: string;
};

export type Publication = PublicationSummary & {
  digest: MarketBrief["digest"]; tldr: MarketBrief["tldr"];
  risks: string[]; suggestions: string[]; evidence_id: string;
  comparison: Pick<SessionBrief, "status" | "changes" | "baseline_label" | "baseline_published_at">;
  notes: { id: string; kind: "correction" | "follow_up"; text: string; created_at: string }[];
  modified_at: string;
};

export function siteUrl(): string | undefined {
  const configured = process.env.PUBLIC_APP_URL;
  if (!configured) return undefined;
  const url = new URL(configured);
  if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) {
    throw new Error("PUBLIC_APP_URL must be an HTTP(S) site origin");
  }
  return url.origin;
}

export const getPublication = cache((slug: string) => fetchApi<Publication>(
  `/api/v2/publications/${encodeURIComponent(slug)}`, { cache: "no-store", next: { revalidate: 0 } },
));
export const getPublications = (limit = 20, offset = 0) =>
  fetchApi<{total: number; items: PublicationSummary[]}>(
    `/api/v2/publications?limit=${limit}&offset=${offset}`, { cache: "no-store", next: { revalidate: 0 } },
  );

export function archivePage(value?: string): number {
  const page = Number(value);
  return Number.isFinite(page) ? Math.min(5000, Math.max(1, Math.floor(page))) : 1;
}

export function socialDraft(article: Publication, origin: string): string {
  const url = new URL(`/briefs/${article.slug}`, origin);
  url.search = new URLSearchParams({ utm_source: "x", utm_medium: "social", utm_campaign: "session_brief" }).toString();
  const label = `${article.as_of.slice(0, 10)} · ${article.label}`;
  // Reserve room for the link, which X counts as a shortened URL.
  const prefix = `Hyperliquid brief · ${label}\n${stanceLabel(article.stance)} · `;
  // Budget two units per character so CJK text also fits an X post.
  const available = Math.max(0, Math.floor((280 - Array.from(prefix).length * 2 - 24 - 2) / 2));
  const characters = Array.from(article.description);
  const read = characters.length > available ? characters.slice(0, available - 1).join("") + "…" : article.description;
  return `${prefix}${read}\n\n${url}`;
}

export function stanceLabel(stance: PublicationSummary["stance"]) {
  return stance === "prefer_long" ? "Prefer longs" : stance === "prefer_short" ? "Prefer shorts" : "Wait";
}
