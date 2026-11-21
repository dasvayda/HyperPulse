import type { MetadataRoute } from "next";
import { getPublications, siteUrl } from "@/lib/publications";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = siteUrl();
  if (!origin) return [];
  const entries: MetadataRoute.Sitemap = [{ url: `${origin}/briefs` }, { url: `${origin}/briefs/methodology` }];
  let offset = 0;
  let total = 1;
  while (offset < total && entries.length < 50000) {
    const page = await getPublications(1000, offset);
    total = page.total;
    entries.push(...page.items.map(item => ({ url: `${origin}/briefs/${item.slug}`, lastModified: item.modified_at })));
    if (!page.items.length) break;
    offset += page.items.length;
  }
  return entries.slice(0, 50000);
}
