import type { PaperEquityPoint } from "@/types";

function pathFor(values: number[], min: number, max: number): string {
  if (values.length === 0) return "";
  const span = Math.max(max - min, 1);
  return values
    .map((value, index) => {
      const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100;
      const y = 92 - ((value - min) / span) * 84;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function PaperEquityChart({ points }: { points: PaperEquityPoint[] }) {
  if (points.length < 2) {
    return (
      <div className="h-64 rounded-xl border border-dashed border-border bg-bg-primary/30 flex items-center justify-center text-sm text-text-dim">
        Equity curve appears after two hourly snapshots.
      </div>
    );
  }
  const strategy = points.map((point) => point.nav);
  const benchmark = points
    .map((point) => point.benchmark_nav)
    .filter((value): value is number => value != null);
  const all = [...strategy, ...benchmark];
  const min = Math.min(...all);
  const max = Math.max(...all);

  return (
    <div className="rounded-xl border border-border bg-bg-primary/30 p-4">
      <div className="flex items-center gap-4 mb-3 text-xs text-text-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-accent" /> HyperPulse
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-text-muted" /> BTC hold
        </span>
        <span className="ml-auto">
          ${min.toFixed(0)} – ${max.toFixed(0)}
        </span>
      </div>
      <svg viewBox="0 0 100 100" className="h-60 w-full" preserveAspectRatio="none" role="img" aria-label="Paper portfolio equity curve">
        {[8, 29, 50, 71, 92].map((y) => (
          <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="currentColor" className="text-border" strokeWidth="0.35" />
        ))}
        {benchmark.length === points.length && (
          <path d={pathFor(benchmark, min, max)} fill="none" stroke="#8b949e" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
        )}
        <path d={pathFor(strategy, min, max)} fill="none" stroke="#00ffa3" strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="flex justify-between mt-2 text-[10px] text-text-dim">
        <span>{new Date(points[0].created_at).toLocaleDateString()}</span>
        <span>{new Date(points[points.length - 1].created_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
}
