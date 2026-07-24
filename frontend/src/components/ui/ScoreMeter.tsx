"use client";

import clsx from "clsx";
import { swingLevelFromRisk, type SwingLevel } from "@/lib/score";

export type { SwingLevel };
export { swingLevelFromRisk };

/** 0–100 score: fill bar implies the max; number has no /100 spam. */
export function ScoreMeter({
  value,
  className,
  size = "md",
}: {
  value: number;
  className?: string;
  size?: "sm" | "md";
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const rounded = Math.round(clamped * 10) / 10;
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);

  return (
    <div
      className={clsx(
        "flex min-w-[5.5rem] items-center gap-2",
        size === "sm" ? "max-w-[7rem]" : "max-w-[8.5rem]",
        className,
      )}
      title={`Score ${text} out of 100`}
    >
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-elevated">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span
        className={clsx(
          "shrink-0 tabular-nums font-semibold text-accent",
          size === "sm" ? "w-7 text-right text-sm" : "w-8 text-right text-base",
        )}
      >
        {text}
      </span>
    </div>
  );
}

export function SwingLabel({
  riskScore,
  className,
}: {
  riskScore: number;
  className?: string;
}) {
  const level = swingLevelFromRisk(riskScore);
  return (
    <span
      className={clsx(
        "text-sm font-medium",
        level === "High" && "text-negative",
        level === "Med" && "text-accent",
        level === "Low" && "text-positive",
        className,
      )}
      title={`ROI swing across Day/Week/Month/All-time windows (raw ${riskScore})`}
    >
      {level}
    </span>
  );
}
