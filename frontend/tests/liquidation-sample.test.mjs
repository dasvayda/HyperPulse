import assert from "node:assert/strict";
import test from "node:test";
import { sampleAmounts } from "../src/lib/liquidation-sample.ts";

const partial = { status: "partial", gap: true, long_usd: null, short_usd: null,
  observed_long_usd: 200, observed_short_usd: 50, events: 2 };
test("partial windows retain only observed amounts", () => {
  assert.deepEqual(sampleAmounts(partial), { available: true, complete: false, long: 200, short: 50 });
});
test("missing or disconnected feeds cannot display a complete zero", () => {
  assert.equal(sampleAmounts().available, false);
  assert.equal(sampleAmounts({ ...partial, status: "unavailable" }).available, false);
});
test("a fully covered zero is valid only inside the wallet sample", () => {
  assert.deepEqual(sampleAmounts({ ...partial, status: "ok", gap: false, long_usd: 0, short_usd: 0 }),
    { available: true, complete: true, long: 0, short: 0 });
});
