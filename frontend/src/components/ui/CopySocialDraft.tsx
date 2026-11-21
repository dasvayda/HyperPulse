"use client";

import { useState } from "react";

export function CopySocialDraft({ text }: { text: string }) {
  const [status, setStatus] = useState("");
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setStatus("Copied");
    } catch {
      setStatus("Select and copy the text below.");
    }
  }
  return <details className="mt-8 rounded-xl border border-border bg-bg-surface p-4">
    <summary className="cursor-pointer text-sm">Share this brief on X</summary>
    <textarea aria-label="X post draft" readOnly value={text} rows={6}
      className="mt-3 w-full rounded-lg border border-border bg-bg-primary p-3 text-sm text-text-primary" />
    <div className="mt-2 flex items-center gap-3">
      <button type="button" onClick={copy} className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-bg-primary">Copy post</button>
      <span role="status" className="text-sm text-text-muted">{status}</span>
    </div>
  </details>;
}
