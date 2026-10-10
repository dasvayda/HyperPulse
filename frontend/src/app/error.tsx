"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <DashboardLayout>
      <div role="alert" className="rounded-xl border border-border bg-bg-surface p-6">
        <p className="text-text-muted">Market data is temporarily unavailable. Try again or choose another page.</p>
        <button onClick={reset} className="mt-4 rounded-lg bg-accent px-4 py-2 text-bg-primary">Try again</button>
      </div>
    </DashboardLayout>
  );
}
