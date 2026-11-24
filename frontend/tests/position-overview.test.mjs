import assert from "node:assert/strict";
import test from "node:test";
import { positionOverview } from "../src/lib/position-overview.ts";

const pos = (asset, side, size_usd, leverage = 1) => ({ asset, side, size_usd, leverage });

test("uses notional weights and groups assets across long and short positions", () => {
  const result = positionOverview([pos("BTC", "long", 60, 10), pos("btc", "short", 20, 30), pos("ETH", "short", 20, 5)]);
  assert.equal(result.longShare, 60);
  assert.equal(result.shortShare, 40);
  assert.equal(result.assetCount, 2);
  assert.deepEqual(result.topAssets[0], { asset: "BTC", share: 80 });
  assert.equal(result.leverage.weighted, 13);
  assert.equal(result.leverage.max, 30);
});

test("shows only the three largest assets, not the full token list", () => {
  const result = positionOverview([pos("BTC", "short", 40), pos("ETH", "short", 30), pos("SOL", "short", 20), pos("HYPE", "short", 10)]);
  assert.equal(result.topShare, 90);
  assert.equal(result.shortShare, 100);
  assert.equal(result.topAssets.length, 3);
  assert.equal(result.assetCount, 4);
});

test("missing leverage is not zero and does not dilute known leverage", () => {
  const result = positionOverview([pos("BTC", "long", 50, null), pos("ETH", "short", 50, 20)]);
  assert.equal(result.leverage.coverage, 50);
  assert.equal(result.leverage.weighted, 20);
  assert.equal(positionOverview([pos("BTC", "long", 50, NaN)]).leverage, null);
});

test("empty or malformed snapshots cannot fabricate a position assessment", () => {
  assert.equal(positionOverview([]), null);
  assert.equal(positionOverview([pos("BTC", "long", NaN), pos("ETH", "short", 0)]), null);
  const result = positionOverview([pos("BTC", "long", 100), pos("SOL", "short", -1)]);
  assert.equal(result.excluded, 1);
  assert.equal(result.longShare, 100);
});
