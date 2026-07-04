"use client";

import clsx from "clsx";

interface SparkBarProps {
  values: number[];
  className?: string;
  color?: "accent" | "positive" | "negative";
}

export function SparkBar({ values, className, color = "accent" }: SparkBarProps) {
  const max = Math.max(...values, 1);

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
          style={{ height: `${(v / max) * 100}%`, minHeight: 2 }}
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

export function SparkBarBackground({
  values,
  children,
  color = "accent",
}: SparkBarBackgroundProps) {
  const max = Math.max(...values, 1);

  const barColor = {
    accent: "bg-accent/15",
    positive: "bg-positive/15",
    negative: "bg-negative/15",
  }[color];

  return (
    <div className="relative flex items-center gap-3">
      <div className="absolute inset-0 flex items-end gap-px opacity-60 pointer-events-none">
        {values.map((v, i) => (
          <div
            key={i}
            className={clsx("flex-1 rounded-sm", barColor)}
            style={{ height: `${(v / max) * 60}%`, minHeight: 2 }}
          />
        ))}
      </div>
      <div className="relative z-10">{children}</div>
    </div>
  );
}
