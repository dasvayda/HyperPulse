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
          change={delivery.queued === 0 ? "No backlog" : "Awaiting delivery"}
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
