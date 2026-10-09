import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  PageHeader,
  StatCard,
} from "@/components/ui/DataTable";
import { AlertFeed } from "@/components/ui/AlertFeed";
import { ExternalLink, Send } from "lucide-react";
import {
  getAlertsHistory,
  getAlertDeliverySummary,
  getPipelineStatus,
  formatTimeAgo,
} from "@/lib/api";

export default async function AlertsPage() {
  const [alerts, pipeline, delivery] = await Promise.all([
    getAlertsHistory(),
    getPipelineStatus(),
    getAlertDeliverySummary(),
  ]);
  const telegramChannelUrl = process.env.NEXT_PUBLIC_TELEGRAM_CHANNEL_URL?.trim();

  return (
    <DashboardLayout>
      <PageHeader
        title="Telegram Alerts"
        description="Big whale moves, liquidation risk, and market reads in one channel"
      />

      <section className="mb-6 rounded-xl border border-border bg-bg-surface p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-lg bg-accent/10 p-2 text-accent">
              <Send className="h-4 w-4" />
            </div>
            <div>
              <h2 className="font-medium text-text-primary">Get alerts on Telegram</h2>
              <p className="mt-1 text-sm text-text-muted">
                Join the channel for major whale moves, LIQ WATCH/DANGER, and the twice-daily Market Brief.
              </p>
            </div>
          </div>
          {telegramChannelUrl ? (
            <a
              href={telegramChannelUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-bg-primary transition-colors hover:bg-accent/90"
            >
              Join Telegram
              <ExternalLink className="h-4 w-4" />
            </a>
          ) : (
            <p className="text-sm text-text-muted">
              Channel access is shared with invited beta users.
            </p>
          )}
        </div>
      </section>

      <section className="mb-6 rounded-xl border border-border bg-bg-surface p-5 text-sm text-text-muted">
        <h2 className="font-medium text-text-primary">Before you join</h2>
        <p className="mt-2">
          All subscribers receive the same channel posts. Coin filters and
          personal alert switches are not available yet. No wallet connection
          or private key is needed to read the channel.
        </p>
        <details className="mt-4">
          <summary className="cursor-pointer text-text-primary">Alert types and timing</summary>
          <ul className="mt-3 list-disc space-y-2 pl-5">
            <li>WHALE MOVE / BIG TRADE: a tracked position changed. “This move” explains the change; “Total position” is the accumulated holding. Only verified fills show a trade price.</li>
            <li>LIQ WATCH / DANGER: a tracked position is close to its reported liquidation price. These warnings use actual wallet liquidation prices.</li>
            <li>Market Brief: scheduled around 09:00 Korea time and 09:00 New York time, once per session when a brief is available. New York time follows daylight saving time.</li>
            <li>Other market reads appear when their thresholds are met. Hourly limits and cooldowns reduce repeated posts, so not every change gets an alert.</li>
          </ul>
          <p className="mt-3">Updates can be delayed by collection or delivery failures. Check the message time and verified wallet details before acting. Quiet periods do not mean that there is no market risk.</p>
        </details>
        <details className="mt-4">
          <summary className="cursor-pointer text-text-primary">Join, mute, or leave</summary>
          <p className="mt-3">Use Join Telegram above, then join the channel in Telegram. Private channels may require the invite shared by the operator.</p>
          <p className="mt-2">Mute notifications in the Telegram channel to keep reading without alerts. To unsubscribe from all posts, leave the channel from its menu. You can return using a valid channel or invite link.</p>
        </details>
      </section>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total Alerts"
          value={String(alerts.length)}
          change={
            pipeline.telegram_configured
              ? "Alert bot connected"
              : "Local queue mode"
          }
          positive={pipeline.telegram_configured}
        />
        <StatCard
          label="Sent (24h)"
          value={String(delivery.sent)}
          change={
            delivery.delivery_rate_pct != null
              ? `${delivery.delivery_rate_pct.toFixed(0)}% delivered`
              : "No attempts yet"
          }
          positive={delivery.failed === 0}
        />
        <StatCard
          label="Queued (24h)"
          value={String(delivery.queued)}
          change={delivery.queued === 0 ? "No queued records" : "Stored locally · not sent"}
          positive={delivery.queued === 0}
        />
        <StatCard
          label="Delivery failures"
          value={String(delivery.failed)}
          change={
            delivery.last_failed_at
              ? `Last ${formatTimeAgo(delivery.last_failed_at)}`
              : pipeline.last_alert_at
                ? `Last alert ${formatTimeAgo(pipeline.last_alert_at)}`
                : "No alerts yet"
          }
          positive={delivery.failed === 0}
        />
      </div>

      <AlertFeed alerts={alerts} />
    </DashboardLayout>
  );
}
