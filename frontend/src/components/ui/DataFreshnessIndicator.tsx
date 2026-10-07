"use client";

import { useEffect, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8100";
const STALE_AFTER_MS = 3 * 60 * 1000;

type PipelineFreshness = {
  collector_enabled: boolean;
  last_collect_at: string | null;
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
        });
        if (!response.ok) return;
        const next = (await response.json()) as PipelineFreshness;
        if (alive) setFreshness(next);
      } catch {
        // The page can still render from its server-fetched data. Avoid turning
        // a transient browser request into a misleading outage message.
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
  return (
    <span
      className={`hidden lg:inline text-xs rounded-lg border px-3 py-1.5 ${
        stale || !freshness.collector_enabled
          ? "border-negative/40 bg-negative/5 text-negative"
          : "border-border bg-bg-surface text-text-muted"
      }`}
      title={
        freshness.last_collect_at
          ? `Last successful collector run: ${freshness.last_collect_at}`
          : "Waiting for the first successful collector run"
      }
    >
      {freshness.collector_enabled ? text : "Collector paused"}
    </span>
  );
}
