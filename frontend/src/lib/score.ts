export type SwingLevel = "Low" | "Med" | "High";

/** Maps legacy risk_score (window ROI volatility, 0–100) to a plain label. */
export function swingLevelFromRisk(riskScore: number): SwingLevel {
  if (riskScore >= 70) return "High";
  if (riskScore >= 45) return "Med";
  return "Low";
}
