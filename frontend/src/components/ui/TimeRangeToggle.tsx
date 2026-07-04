"use client";

import clsx from "clsx";

interface TimeRangeToggleProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function TimeRangeToggle({
  options,
  value,
  onChange,
  className,
}: TimeRangeToggleProps) {
  return (
    <div className={clsx("flex items-center gap-1", className)}>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={clsx(
            "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
            value === opt
              ? "border border-accent text-accent bg-accent/5"
              : "border border-transparent text-text-muted hover:text-text-primary hover:bg-bg-elevated",
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

interface PillToggleProps {
  options: { label: string; value: string }[];
  value: string;
  onChange: (value: string) => void;
}

export function PillToggle({ options, value, onChange }: PillToggleProps) {
  return (
    <div className="flex items-center rounded-xl bg-bg-elevated p-1 border border-border">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={clsx(
            "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors",
            value === opt.value
              ? "bg-bg-hover text-text-primary"
              : "text-text-muted hover:text-text-primary",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
