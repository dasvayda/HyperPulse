"use client";

import { useEffect, useState } from "react";

const KEY = "hyperpulse-beta-visit";
type Event = "session_view" | "telegram_evidence" | "scorecard_view";

export function BetaVisit({ event, subject = "" }: { event: Event; subject?: string }) {
  const [visitor, setVisitor] = useState<string | null>(null);
  useEffect(() => {
    try { setVisitor(localStorage.getItem(KEY)); } catch { /* storage blocked */ }
  }, []);
  useEffect(() => {
    if (!visitor) return;
    void fetch("/api/beta/visits", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visitor, event, subject }),
    }).catch(() => {});
  }, [visitor, event, subject]);
  return <div className="mt-3 text-xs text-text-muted">
  <p>Optional Beta measurement uses a random browser ID to count visits, not wallet activity. Turning it off stops future measurement on this browser.</p>
  <button type="button" className="mt-1 underline" onClick={() => {
    try {
      if (visitor) {
        localStorage.removeItem(KEY);
        setVisitor(null);
      } else {
        const id = crypto.randomUUID();
        localStorage.setItem(KEY, id);
        setVisitor(id);
      }
    } catch { /* no tracking without storage */ }
  }}>{visitor ? "Stop optional Beta visit measurement" : "Allow optional Beta visit measurement"}</button>
  </div>;
}
