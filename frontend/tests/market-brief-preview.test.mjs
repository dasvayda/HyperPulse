import assert from "node:assert/strict";
import test from "node:test";
import { marketBriefPreview } from "../src/lib/market-brief-preview.ts";

const brief = {
  headline: "Market headline", risks: ["Prices can move against the book."],
  tldr: { now: "BTC tape and funding", short_read: "Old read", however: "Wait for confirmation." },
  digest: { read: "Short-heavy book is not price confirmation.", as_of_line: "Digest tape" },
};

test("analysis takes priority over market tape and retains the caution", () => {
  assert.deepEqual(marketBriefPreview(brief), {
    read: brief.digest.read, context: brief.tldr.now, caution: brief.tldr.however,
  });
});
test("older briefs use short_read when digest read is blank", () => {
  assert.equal(marketBriefPreview({ ...brief, digest: { read: "  " } }).read, "Old read");
});
test("digest-only briefs preserve context and risk", () => {
  const result = marketBriefPreview({ ...brief, tldr: null });
  assert.equal(result.context, "Digest tape");
  assert.equal(result.caution, brief.risks[0]);
});
test("headline-only data is not presented as an analysis", () => {
  const result = marketBriefPreview({ headline: "BTC $80K", risks: [] });
  assert.match(result.read, /Analysis is not available/);
  assert.equal(result.context, "BTC $80K");
});
test("missing brief has an explicit unavailable state", () => {
  assert.match(marketBriefPreview(null).read, /temporarily unavailable/);
  assert.equal(marketBriefPreview(null).context, null);
});
test("long analysis is preserved without truncation", () => {
  const read = "Use positioning as context, not confirmation. ".repeat(15).trim();
  assert.equal(marketBriefPreview({ ...brief, digest: { read } }).read, read);
});
test("duplicate copy is not repeated", () => {
  const result = marketBriefPreview({ ...brief, tldr: { now: brief.digest.read, however: brief.digest.read } });
  assert.equal(result.context, null);
  assert.equal(result.caution, null);
});
