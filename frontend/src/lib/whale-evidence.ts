const actions: Record<string, string> = {
  entry: "Opened", increase: "Added", reduce: "Trimmed", close: "Closed", flip: "Flipped",
};

export function whaleEvidenceSummary(inputs: Record<string, unknown>) {
  const value = inputs.trigger;
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  if (typeof row.trader_address !== "string" || !/^0x[0-9a-f]{40}$/i.test(row.trader_address)
      || typeof row.asset !== "string" || !["long", "short"].includes(String(row.side))) return null;
  const valid = (number: unknown): number | null => typeof number === "number" && Number.isFinite(number) ? number : null;
  const execution = row.execution as Record<string, unknown> | null;
  const prior = row.prior_reduction as Record<string, unknown> | null;
  const priorFill = prior?.execution as Record<string, unknown> | null;
  return {
    address: row.trader_address,
    asset: row.asset,
    side: String(row.side).toUpperCase(),
    action: actions[String(row.position_change)] ?? "Position changed",
    observed: typeof row.position_observed_at === "string" ? row.position_observed_at : String(row.timestamp ?? ""),
    delta: valid(row.size_delta_usd),
    total: valid(row.size_usd),
    fill: execution?.verified === true ? valid(execution.notional_usd) : null,
    low: execution?.verified === true ? valid(execution.price_low) : null,
    high: execution?.verified === true ? valid(execution.price_high) : null,
    priorTrim: priorFill?.verified === true ? valid(priorFill.notional_usd) : null,
  };
}
