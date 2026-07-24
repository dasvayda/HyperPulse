"use client";

import clsx from "clsx";

interface SparkBarProps {
  values: number[];
  className?: string;
  color?: "accent" | "positive" | "negative";
}

export function SparkBar({ values, className, color = "accent" }: SparkBarProps) {
  const max = Math.max(...values.map((v) => Math.abs(v)), 1);

  const barColor = {
    accent: "bg-accent/40",
    positive: "bg-positive/40",
    negative: "bg-negative/40",
  }[color];

  return (
    <div className={clsx("flex items-end gap-px h-5", className)}>
      {values.map((v, i) => (
        <div
          key={i}
          className={clsx("w-1 rounded-sm", barColor)}
          style={{ height: `${(Math.abs(v) / max) * 100}%`, minHeight: 2 }}
        />
      ))}
    </div>
  );
}

interface SparkBarBackgroundProps {
  values: number[];
  children: React.ReactNode;
  color?: "accent" | "positive" | "negative";
}

/** Decorative bars behind a label (score, etc.). Prefer WindowPnlBars for trader PnL. */
export function SparkBarBackground({
  values,
  children,
  color = "accent",
}: SparkBarBackgroundProps) {
  const series = values.slice(0, 3);
  const max = Math.max(...series.map((v) => Math.abs(v)), 1);

  const barColor = {
    accent: "bg-accent/45",
    positive: "bg-positive/45",
    negative: "bg-negative/45",
  }[color];

  return (
    <div className="relative flex min-h-8 min-w-[5.5rem] items-center gap-3">
      <div className="absolute inset-0 flex items-end gap-0.5 opacity-90 pointer-events-none">
        {series.map((v, i) => (
          <div
            key={i}
            className={clsx("flex-1 rounded-sm", barColor)}
            style={{
              height: `${Math.max(12, (Math.abs(v) / max) * 85)}%`,
              minHeight: 4,
            }}
          />
        ))}
      </div>
      <div className="relative z-10 drop-shadow-[0_0_6px_rgba(0,0,0,0.85)]">
        {children}
      </div>
    </div>
  );
}

interface WindowPnlBarsProps {
  /** Leaderboard windows: [day, week, month, allTime?] — allTime is dropped (shown elsewhere). */
  values: number[];
  className?: string;
}

/**
 * Day / Week / Month PnL bars (not an equity curve).
 * Green = profit in that window, red = loss. Heights compare those three only.
 */
export function WindowPnlBars({ values, className }: WindowPnlBarsProps) {
  const windows = values.slice(0, 3);
  if (windows.length === 0) {
    return <span className="text-xs text-text-dim">—</span>;
  }

  const max = Math.max(...windows.map((v) => Math.abs(v)), 1);
  const labels = ["D", "W", "M"] as const;

  return (
    <div
      className={clsx("flex min-w-[4.75rem] flex-col gap-0.5", className)}
      title="Day / Week / Month PnL (not an equity curve)"
    >
      <div className="flex h-6 items-end gap-1">
        {windows.map((v, i) => (
          <div
            key={labels[i] ?? i}
            className="flex h-full flex-1 flex-col items-center justify-end"
          >
            <div
              className={clsx(
                "w-full max-w-[11px] rounded-sm",
                v >= 0 ? "bg-positive/75" : "bg-negative/75",
              )}
              style={{
                height: `${Math.max(10, (Math.abs(v) / max) * 100)}%`,
              }}
            />
          </div>
        ))}
      </div>
      <div className="flex gap-1">
        {windows.map((_, i) => (
          <span
            key={labels[i]}
            className="flex-1 text-center text-[9px] leading-none text-text-dim"
          >
            {labels[i]}
          </span>
        ))}
      </div>
    </div>
  );
}
