import assert from "node:assert/strict";
import test from "node:test";
import { whaleEvidenceSummary } from "../src/lib/whale-evidence.ts";

test("verified prior trim does not verify a close or expose its unconfirmed price", () => {
  const result = whaleEvidenceSummary({trigger: {
    trader_address: "0x" + "a".repeat(40), asset: "ZEC", side: "short", position_change: "close",
    size_usd: 0, execution: {verified: false, notional_usd: 3e6, price_low: 884},
    prior_reduction: {execution: {verified: true, notional_usd: 3e6}},
  }});
  assert.equal(result.action, "Closed");
  assert.equal(result.total, 0);
  assert.equal(result.fill, null);
  assert.equal(result.low, null);
  assert.equal(result.priorTrim, 3e6);
});
