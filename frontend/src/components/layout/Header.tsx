"use client";

import { Search } from "lucide-react";
import { DataFreshnessIndicator } from "@/components/ui/DataFreshnessIndicator";

export function Header() {
  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-2 border-b border-border bg-bg-primary/80 px-4 py-3 backdrop-blur-md sm:px-6">
      <div className="flex w-full min-w-0 items-center gap-3 sm:w-auto sm:max-w-md sm:flex-1">
        <div className="relative min-w-0 flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-dim" />
          <input
            type="text"
            placeholder="Search traders, assets..."
            className="w-full bg-bg-surface border border-border rounded-lg pl-9 pr-16 py-2 text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-accent/50 transition-colors"
          />
          <kbd className="absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-bg-elevated px-1.5 py-0.5 text-xs text-text-dim xl:block">
            Ctrl K
          </kbd>
        </div>
      </div>

      <div className="flex min-w-0 flex-wrap items-center gap-2 sm:gap-3">
        <DataFreshnessIndicator />
        <span className="hidden xl:inline text-xs text-text-muted bg-bg-surface border border-border rounded-lg px-3 py-1.5">
          Hyperliquid Intelligence Platform
        </span>
        <button className="text-sm text-text-muted hover:text-text-primary transition-colors px-3 py-1.5">
          Sign In
        </button>
        <button className="text-sm font-medium bg-accent text-bg-primary rounded-full px-4 py-1.5 hover:bg-accent/90 transition-colors">
          Sign Up
        </button>
      </div>
    </header>
  );
}
