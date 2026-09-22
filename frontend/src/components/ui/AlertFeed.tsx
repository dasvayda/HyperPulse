import { Badge } from "@/components/ui/Badge";
import type { AlertHistoryItem } from "@/types";
import { formatTimeAgo } from "@/lib/api";

interface AlertFeedProps {
  alerts: AlertHistoryItem[];
  className?: string;
  limit?: number;
}

const statusVariant: Record<string, "accent" | "default" | "short"> = {
  sent: "accent",
  queued: "default",
  failed: "short",
};

/** Drop the title line when the stored message repeats it (Telegram payload). */
function alertBody(title: string, message: string): string {
  const lines = message
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  const body =
    lines[0]?.toLowerCase() === title.trim().toLowerCase()
      ? lines.slice(1)
      : lines;
  return body.join(" · ") || message;
}

export function AlertFeed({
  alerts,
  className = "",
  limit = 6,
}: AlertFeedProps) {
  const items = alerts.slice(0, limit);

  if (items.length === 0) {
    return (
      <div
        className={`rounded-xl border border-border bg-bg-surface p-5 text-sm text-text-muted ${className}`}
      >
        No alerts yet. Pipeline will queue Telegram notifications when thresholds are met.
      </div>
    );
  }

  return (
    <div
      className={`rounded-xl border border-border bg-bg-surface divide-y divide-border-subtle overflow-hidden ${className}`}
    >
      {items.map((alert) => (
        <div key={alert.id} className="p-4 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-text-primary">{alert.title}</p>
            <div className="flex items-center gap-2 shrink-0">
              <Badge variant={statusVariant[alert.status] ?? "default"}>
                {alert.status}
              </Badge>
              <span className="text-xs text-text-dim">
                {formatTimeAgo(alert.created_at)}
              </span>
            </div>
          </div>
          <p className="text-xs text-text-muted leading-relaxed line-clamp-3">
            {alertBody(alert.title, alert.message)}
          </p>
          <p className="text-xs text-text-dim">
            {alert.channel} · {alert.event_type}
          </p>
        </div>
      ))}
    </div>
  );
}
