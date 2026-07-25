"use client";

import { useEffect, useState } from "react";
import { InsightCard } from "@/components/ui/InsightCard";
import type { MarketInsight } from "@/types";

const ROTATE_MS = 8000;

interface InsightCardCarouselProps {
  insights: MarketInsight[];
  className?: string;
}

export function InsightCardCarousel({
  insights,
  className = "",
}: InsightCardCarouselProps) {
  const [index, setIndex] = useState(0);
  const [pausedUntil, setPausedUntil] = useState(0);

  const count = insights.length;

  useEffect(() => {
    if (count <= 1) return;
    const id = window.setInterval(() => {
      if (Date.now() < pausedUntil) return;
      setIndex((prev) => (prev + 1) % count);
    }, ROTATE_MS);
    return () => window.clearInterval(id);
  }, [count, pausedUntil]);

  useEffect(() => {
    if (index >= count) setIndex(0);
  }, [count, index]);

  if (count === 0) {
    return (
      <div
        className={`rounded-xl border border-border border-dashed bg-bg-surface/50 p-5 flex items-center justify-center text-center min-h-[200px] ${className}`}
      >
        <p className="text-sm text-text-dim">
          Prefer cards appear after whale book + funding/liq signals are ready.
        </p>
      </div>
    );
  }

  const current = insights[Math.min(index, count - 1)];

  function goTo(next: number) {
    setIndex(next);
    setPausedUntil(Date.now() + ROTATE_MS * 2);
  }

  return (
    <div className={`relative w-full ${className}`}>
      <InsightCard insight={current} className="h-full pb-8" />
      {count > 1 && (
        <div
          className="absolute bottom-4 right-4 flex items-center gap-1.5 z-10"
          role="tablist"
          aria-label="Prefer card pages"
        >
          {insights.map((item, i) => {
            const active = i === index;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={active}
                aria-label={`Show card ${i + 1}: ${item.title}`}
                onClick={() => goTo(i)}
                className={`h-2 w-2 rounded-full transition-opacity ${
                  active
                    ? "bg-white opacity-100"
                    : "bg-white/40 hover:bg-white/70 opacity-80"
                }`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
