import { ImageResponse } from "next/og";

export const alt = "HyperPulse — Hyperliquid market briefs";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(<div style={{ display: "flex", flexDirection: "column", justifyContent: "center", width: "100%", height: "100%", background: "#0b0e11", color: "white", padding: 80 }}>
    <div style={{ color: "#00ffa3", fontSize: 32 }}>HyperPulse</div>
    <div style={{ fontSize: 72, marginTop: 30 }}>Hyperliquid market briefs</div>
    <div style={{ color: "#8b949e", fontSize: 30, marginTop: 30 }}>Whale positions · Funding · What changed</div>
  </div>, size);
}
