import { Badge } from "@/components/ui/Badge";
import type { AlertHistoryItem } from "@/types";
import { formatTimeAgo } from "@/lib/api";

interface AlertFeedProps {
  alerts: AlertHistoryItem[];
  className?: string;
  limit?: number;
  /** Home preview only; the alerts page retains its detailed layout. */
  compact?: boolean;
}

const statusVariant: Record<string, "accent" | "default" | "short"> = {
  sent: "accent",
  queued: "default",
  failed: "short",
};

/** Historical Telegram rows preserve their payload, but not misleading copy. */
function isLegacySnapshotCopy(title: string, message: string): boolean {
  return /\b(one-shot|added)\b|FRESH ENTRY|\b(?:LONG|SHORT) (?:IN|OUT)\b/i.test(
    `${title}\n${message}`,
  );
}

function displayAlertTitle(title: string): string {
  return title
    .replace(/FRESH ENTRY/gi, "POSITION UP")
    .replace(/\b(LONG|SHORT) IN\b/gi, "$1 POSITION UP")
    .replace(/\b(LONG|SHORT) OUT\b/gi, "$1 POSITION DOWN");
}

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
  return (body.join(" · ") || message)
    .replace(/\bone-shot\b/gi, "position")
    .replace(/ · entry /gi, " · avg entry ")
    .replace(/ · added /gi, " · snapshot change ")
    .replace(/\b(?:entered|exited) (LONG|SHORT) /gi, "$1 position ");
}

export function AlertFeed({
  alerts,
  className = "",
  limit = 6,
  compact = false,
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
      {items.map((alert) => {
        const legacySnapshot = isLegacySnapshotCopy(alert.title, alert.message);
        return (
        <div key={alert.id} className="p-4 flex flex-col gap-2">
          <div className={compact ? "flex flex-col gap-2" : "flex items-center justify-between gap-3"}>
            <p className={`text-sm font-medium text-text-primary ${compact ? "line-clamp-2" : ""}`}>{displayAlertTitle(alert.title)}</p>
            <div className={`flex items-center gap-2 shrink-0 ${compact ? "justify-between" : ""}`}>
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
          {!compact ? <p className="text-xs text-text-dim">
            {alert.channel} · {alert.event_type}
          </p> : null}
          {legacySnapshot ? (
            <p className="text-xs text-text-dim">
              Legacy snapshot alert · fills not verified
            </p>
          ) : compact && /fills not verified|unverified/i.test(alert.message) ? (
            <p className="text-xs text-text-dim">Fills not verified — check the wallet before acting.</p>
          ) : null}
        </div>
        );
      })}
    </div>
  );
}
