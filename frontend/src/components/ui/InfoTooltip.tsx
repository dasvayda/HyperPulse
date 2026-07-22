"use client";

import { useId, useState, type ReactNode } from "react";

interface InfoTooltipProps {
  label: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Hover/focus tooltip that escapes table overflow clipping via fixed position. */
export function InfoTooltip({ label, children, className = "" }: InfoTooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });

  function place(el: HTMLElement) {
    const rect = el.getBoundingClientRect();
    setCoords({
      top: rect.bottom + 8,
      left: Math.min(rect.left, window.innerWidth - 300),
    });
  }

  return (
    <span className={`inline-flex items-center gap-1 ${className}`}>
      <span>{label}</span>
      <button
        type="button"
        aria-describedby={open ? id : undefined}
        className="text-text-dim cursor-help text-[11px] leading-none rounded-sm hover:text-text-muted focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        onMouseEnter={(e) => {
          place(e.currentTarget);
          setOpen(true);
        }}
        onMouseLeave={() => setOpen(false)}
        onFocus={(e) => {
          place(e.currentTarget);
          setOpen(true);
        }}
        onBlur={() => setOpen(false)}
      >
        ⓘ
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="fixed z-[80] w-72 rounded-lg border border-border bg-bg-elevated p-3 text-left text-[11px] font-normal leading-relaxed text-text-muted shadow-lg"
          style={{ top: coords.top, left: coords.left }}
        >
          {children}
        </span>
      )}
    </span>
  );
}
