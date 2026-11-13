import type { SessionBrief } from "../types";

export function describeSessionChange({ asset, metric, delta }: SessionBrief["changes"][number]) {
  const sign = delta > 0 ? "+" : "";
  if (metric === "mark") return `${asset} mark ${sign}${delta.toFixed(2)}%`;
  if (metric === "funding") return `${asset} hourly funding ${sign}${delta.toFixed(4)} pp`;
  return `${asset} tracked whale long share ${sign}${delta.toFixed(1)} pp`;
}

export function sessionComparisonNote(status: SessionBrief["status"], hasChanges: boolean) {
  switch (status) {
    case "no_baseline": return "First published session. No prior brief to compare.";
    case "unavailable": return "Session inputs are missing, delayed or not comparable.";
    case "partial": return hasChanges
      ? "Only comparable inputs shown. Some data was delayed, missing or from a different sample."
      : "No large change in comparable inputs. Some data could not be compared.";
    case "unchanged": return "No large change since the previous session.";
    case "changed": return null;
  }
}
