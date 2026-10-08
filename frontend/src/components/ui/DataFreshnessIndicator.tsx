"use client";

import { useEffect, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";
const STALE_AFTER_MS = 3 * 60 * 1000;

type PipelineFreshness = {
  collector_enabled: boolean;
  last_collect_at: string | null;
  collectors?: Record<string, { status: string; successful: number; expected: number }>;
};

function labelFor(lastCollectAt: string | null): { text: string; stale: boolean } {
  if (!lastCollectAt) return { text: "Data warming up", stale: true };
  const ageMs = Date.now() - new Date(lastCollectAt).getTime();
  if (Number.isNaN(ageMs)) return { text: "Data time unavailable", stale: true };
  const mins = Math.max(0, Math.floor(ageMs / 60_000));
  if (ageMs > STALE_AFTER_MS) return { text: `Data delayed · ${mins}m ago`, stale: true };
  return { text: `Live data · ${mins}m ago`, stale: false };
}

export function DataFreshnessIndicator() {
  const [freshness, setFreshness] = useState<PipelineFreshness | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const response = await fetch(`${API_URL}/api/v2/pipeline/status`, {
          cache: "no-store",
          signal: AbortSignal.timeout(5_000),
        });
        if (!response.ok) throw new Error("Status unavailable");
        const next = (await response.json()) as PipelineFreshness;
        if (alive) setFreshness(next);
      } catch {
        if (alive) setFreshness((previous) => previous ? {
          ...previous,
          collectors: { ...previous.collectors, status_check: { status: "error", successful: 0, expected: 1 } },
        } : { collector_enabled: true, last_collect_at: null,
          collectors: { status_check: { status: "error", successful: 0, expected: 1 } } });
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  if (!freshness) return null;
  const { text, stale } = labelFor(freshness.last_collect_at);
  const failed = Object.entries(freshness.collectors ?? {}).filter(([, state]) => state.status !== "ok");
  const degraded = failed.length > 0;
  return (
    <span
      className={`inline text-xs rounded-lg border px-3 py-1.5 ${
        stale || degraded || !freshness.collector_enabled
          ? "border-negative/40 bg-negative/5 text-negative"
          : "border-border bg-bg-surface text-text-muted"
      }`}
      title={
        freshness.last_collect_at
          ? `Last successful market collection: ${freshness.last_collect_at}${failed.map(([name, state]) => `; ${name}: ${state.successful}/${state.expected} successful`).join("")}`
          : "Waiting for the first successful collector run"
      }
    >
      {freshness.collector_enabled ? degraded ? `Data incomplete · ${failed.map(([name]) => name.replace("status_check", "status unavailable")).join(", ")}` : text : "Collector paused"}
    </span>
  );
}
