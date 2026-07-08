import { Badge } from "@/components/ui/Badge";
import type { AlertHistoryItem } from "@/types";
import { formatTimeAgo } from "@/lib/api";

interface AlertFeedProps {
  alerts: AlertHistoryItem[];
}

const statusVariant: Record<string, "accent" | "default" | "short"> = {
  sent: "accent",
  queued: "default",
  failed: "short",
};

export function AlertFeed({ alerts }: AlertFeedProps) {
  if (alerts.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-bg-surface p-5 text-sm text-text-muted">
        No alerts yet. Pipeline will queue Telegram notifications when thresholds are met.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-bg-surface divide-y divide-border-subtle max-h-[360px] overflow-y-auto">
      {alerts.map((alert) => (
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
          <p className="text-xs text-text-muted leading-relaxed line-clamp-2">
            {alert.message}
          </p>
          <p className="text-xs text-text-dim">
            {alert.channel} · {alert.event_type}
          </p>
        </div>
      ))}
    </div>
  );
}
