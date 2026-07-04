"use client";

import { Search } from "lucide-react";

export function Header() {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-6 py-3 bg-bg-primary/80 backdrop-blur-md border-b border-border">
      <div className="flex items-center gap-3 flex-1 max-w-md">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-dim" />
          <input
            type="text"
            placeholder="Search traders, assets..."
            className="w-full bg-bg-surface border border-border rounded-lg pl-9 pr-16 py-2 text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-accent/50 transition-colors"
          />
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-dim bg-bg-elevated border border-border rounded px-1.5 py-0.5">
            Ctrl K
          </kbd>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="hidden md:inline text-xs text-text-muted bg-bg-surface border border-border rounded-lg px-3 py-1.5">
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
