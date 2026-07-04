import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  PageHeader,
  StatCard,
} from "@/components/ui/DataTable";
import { AlertFeed } from "@/components/ui/AlertFeed";
import {
  getAlertsHistory,
  getPipelineStatus,
  formatTimeAgo,
} from "@/lib/api";

export default async function AlertsPage() {
  const [alerts, pipeline] = await Promise.all([
    getAlertsHistory(),
    getPipelineStatus(),
  ]);

  const sent = alerts.filter((a) => a.status === "sent").length;
  const queued = alerts.filter((a) => a.status === "queued").length;
  const failed = alerts.filter((a) => a.status === "failed").length;

  return (
    <DashboardLayout>
      <PageHeader
        title="Telegram Alerts"
        description="Whale entries, squeeze risk, and strategy inference notifications"
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Total Alerts"
          value={String(alerts.length)}
          change={
            pipeline.telegram_configured
              ? "Telegram connected"
              : "Local queue mode"
          }
          positive={pipeline.telegram_configured}
        />
        <StatCard label="Sent" value={String(sent)} change="Delivered" positive />
        <StatCard
          label="Queued"
          value={String(queued)}
          change="Awaiting bot token"
          positive={queued === 0}
        />
        <StatCard
          label="Last Alert"
          value={
            pipeline.last_alert_at
              ? formatTimeAgo(pipeline.last_alert_at)
              : "—"
          }
          change={`${failed} failed`}
          positive={failed === 0}
        />
      </div>

      <AlertFeed alerts={alerts} />
    </DashboardLayout>
  );
}
