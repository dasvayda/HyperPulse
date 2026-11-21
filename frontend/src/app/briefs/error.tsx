"use client";

export default function BriefError({ reset }: { reset: () => void }) {
  return <div role="alert">
    <h1 className="text-2xl font-semibold">Published briefs are temporarily unavailable</h1>
    <p className="mt-3 text-text-muted">Try loading the archive again.</p>
    <button onClick={reset} className="mt-5 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-bg-primary">Try again</button>
  </div>;
}
