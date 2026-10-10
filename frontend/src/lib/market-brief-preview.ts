import type { MarketBrief } from "@/types";

/** Keep the read separate from tape; a headline alone is not an analysis. */
export function marketBriefPreview(brief: MarketBrief | null) {
  const read = brief?.digest?.read?.trim() || brief?.tldr?.short_read?.trim();
  const context = brief?.tldr?.now?.trim() || brief?.digest?.as_of_line?.trim() || brief?.headline?.trim();
  const caution = brief?.tldr?.however?.trim() || brief?.risks?.find((risk) => risk.trim());
  return {
    read: read || (brief
      ? "Analysis is not available yet — check the market data and full brief."
      : "Brief temporarily unavailable — check the live market data below."),
    context: context && context !== read ? context : null,
    caution: caution && caution !== read && caution !== context ? caution : null,
  };
}
