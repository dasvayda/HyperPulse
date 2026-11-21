import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/publications";

export default function robots(): MetadataRoute.Robots {
  const origin = siteUrl();
  return { rules: [{ userAgent: "*", allow: "/briefs", disallow: "/api/" }],
    sitemap: origin ? `${origin}/sitemap.xml` : undefined };
}
