import assert from "node:assert/strict";
import test from "node:test";
import { describeSessionChange, sessionComparisonNote } from "../src/lib/session-brief-copy.ts";

test("relative mark changes and percentage-point changes stay distinct", () => {
  assert.equal(describeSessionChange({asset: "BTC", metric: "mark", delta: 2}), "BTC mark +2.00%");
  assert.equal(describeSessionChange({asset: "BTC", metric: "funding", delta: -0.01}), "BTC hourly funding -0.0100 pp");
  assert.equal(describeSessionChange({asset: "BTC", metric: "whale_long_share", delta: 5}), "BTC tracked whale long share +5.0 pp");
});

test("missing and partial comparisons never look like a full unchanged session", () => {
  assert.match(sessionComparisonNote("no_baseline", false), /No prior/);
  assert.match(sessionComparisonNote("unavailable", false), /missing/);
  assert.match(sessionComparisonNote("partial", false), /could not be compared/);
  assert.match(sessionComparisonNote("partial", true), /Only comparable/);
  assert.match(sessionComparisonNote("unchanged", false), /previous session/);
  assert.equal(sessionComparisonNote("changed", true), null);
});
