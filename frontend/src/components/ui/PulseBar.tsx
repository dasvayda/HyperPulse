import type { PulseDirection, PulseSnapshot } from "@/types";

function horizonLabel(sec: number): string {
  if (sec % 60 === 0) return `${sec / 60}m`;
  return `${sec}s`;
}

function directionPct(pulse: PulseSnapshot): { label: string; pct: number } {
  const map: Record<PulseDirection, { label: string; pct: number }> = {
    up: { label: "up", pct: pulse.p_up },
    down: { label: "down", pct: pulse.p_down },
    wait: { label: "wait", pct: pulse.p_wait },
  };
  return map[pulse.direction];
}

export function pulseLine(pulse: PulseSnapshot): string {
  const { label, pct } = directionPct(pulse);
  const head = `${horizonLabel(pulse.horizon_sec)} pulse · ${(pct * 100).toFixed(0)}% ${label}`;
  if (pulse.warming_up || pulse.hit_rate == null) {
    return `${head} · warming up`;
  }
  const hits = Math.round(pulse.hit_rate * pulse.hit_n);
  return `${head} · ${hits}/${pulse.hit_n} hit`;
}

export function pulseChipLabel(pulse: PulseSnapshot): string {
  const { label, pct } = directionPct(pulse);
  return `${horizonLabel(pulse.horizon_sec)} ${pulse.asset} ${(pct * 100).toFixed(0)}% ${label}`;
}

interface PulseBarProps {
  pulse: PulseSnapshot;
  compact?: boolean;
}

export function PulseBar({ pulse, compact = false }: PulseBarProps) {
  const up = Math.max(0, pulse.p_up * 100);
  const wait = Math.max(0, pulse.p_wait * 100);
  const down = Math.max(0, pulse.p_down * 100);

  return (
    <div className={compact ? "space-y-1" : "space-y-1.5"}>
      {!compact ? (
        <p className="text-[11px] text-text-dim">{pulseLine(pulse)}</p>
      ) : null}
      <div
        className="flex h-1.5 w-full overflow-hidden rounded-full bg-bg-elevated"
        title={`up ${(up).toFixed(0)}% · wait ${(wait).toFixed(0)}% · down ${(down).toFixed(0)}%`}
      >
        <span className="bg-positive" style={{ width: `${up}%` }} />
        <span className="bg-text-dim/50" style={{ width: `${wait}%` }} />
        <span className="bg-negative" style={{ width: `${down}%` }} />
      </div>
      <div className="flex gap-0.5">
        {pulse.ticks
          .slice()
          .reverse()
          .map((tick, idx) => {
            const color =
              tick.direction === "up"
                ? "border-positive"
                : tick.direction === "down"
                  ? "border-negative"
                  : "border-text-dim";
            const fill =
              tick.hit === true
                ? tick.direction === "up"
                  ? "bg-positive"
                  : tick.direction === "down"
                    ? "bg-negative"
                    : "bg-text-dim"
                : tick.hit === false
                  ? "bg-transparent opacity-40"
                  : "bg-transparent";
            return (
              <span
                key={`${tick.created_at}-${idx}`}
                className={`h-2 w-2 rounded-[2px] border ${color} ${fill}`}
                title={`${tick.direction}${tick.hit == null ? " (open)" : tick.hit ? " hit" : " miss"}`}
              />
            );
          })}
      </div>
    </div>
  );
}
