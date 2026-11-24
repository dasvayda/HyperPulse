type Position = { asset: string; side: "long" | "short"; size_usd: number; leverage: number };

/** Gross open notional, not account equity, historical trading or net exposure. */
export function positionOverview(positions: readonly Position[]) {
  const valid = positions.filter(p => Number.isFinite(p.size_usd) && p.size_usd > 0 &&
    p.asset.trim() && (p.side === "long" || p.side === "short"));
  const total = valid.reduce((sum, p) => sum + p.size_usd, 0);
  if (!Number.isFinite(total) || total <= 0) return null;
  const long = valid.filter(p => p.side === "long").reduce((sum, p) => sum + p.size_usd, 0);
  const byAsset = new Map<string, number>();
  for (const p of valid) {
    const asset = p.asset.trim().toUpperCase();
    byAsset.set(asset, (byAsset.get(asset) ?? 0) + p.size_usd);
  }
  const assets = [...byAsset].map(([asset, notional]) => ({ asset, share: notional / total * 100 }))
    .sort((a, b) => b.share - a.share || a.asset.localeCompare(b.asset));
  const leveraged = valid.filter(p => Number.isFinite(p.leverage) && p.leverage > 0);
  const covered = leveraged.reduce((sum, p) => sum + p.size_usd, 0);
  return {
    longShare: long / total * 100,
    shortShare: (total - long) / total * 100,
    assetCount: assets.length,
    topAssets: assets.slice(0, 3),
    topShare: assets.slice(0, 3).reduce((sum, a) => sum + a.share, 0),
    leverage: covered > 0 ? {
      weighted: leveraged.reduce((sum, p) => sum + p.leverage * (p.size_usd / covered), 0),
      min: Math.min(...leveraged.map(p => p.leverage)),
      max: Math.max(...leveraged.map(p => p.leverage)),
      coverage: covered / total * 100,
    } : null,
    excluded: positions.length - valid.length,
  };
}
