import { test } from "node:test";
import assert from "node:assert/strict";
import { matchesBetaLogin } from "../src/lib/beta-access.ts";

const basic = (value) => "Basic " + Buffer.from(value).toString("base64");

test("beta login requires the correct username and secret", async () => {
  assert.equal(await matchesBetaLogin(basic("beta:test-secret"), "test-secret"), true);
  assert.equal(await matchesBetaLogin(basic("other:test-secret"), "test-secret"), false);
  assert.equal(await matchesBetaLogin(basic("beta:wrong-secret"), "test-secret"), false);
});

test("missing, malformed and oversized credentials fail closed", async () => {
  for (const value of [null, "Basic !!", "Bearer test-secret", "Basic " + "A".repeat(4096)]) {
    assert.equal(await matchesBetaLogin(value, "test-secret"), false);
  }
  assert.equal(await matchesBetaLogin(basic("beta:"), ""), false);
});
