import { DashboardLayout } from "@/components/layout/DashboardLayout";

export default function Loading() {
  return (
    <DashboardLayout>
      <div role="status" className="rounded-xl border border-border bg-bg-surface p-6 text-text-muted">
        Loading market data… You can still choose another page.
      </div>
    </DashboardLayout>
  );
}
