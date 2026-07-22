"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  Home,
  Bell,
  Users,
  Flame,
  Activity,
  Settings,
  Brain,
  Trophy,
  Send,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/whale-alerts", label: "Whale Alerts", icon: Bell },
  { href: "/traders", label: "Ranking", icon: Trophy },
  { href: "/rankings", label: "Smart Money", icon: Users },
  { href: "/insights", label: "AI Insights", icon: Brain },
  { href: "/liquidations", label: "Liquidations", icon: Flame },
  { href: "/alerts", label: "Alerts", icon: Send },
];

const SECONDARY_ITEMS = [
  { href: "/activity", label: "Activity", icon: Activity, disabled: true },
  { href: "/settings", label: "Settings", icon: Settings, disabled: true },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-[220px] bg-bg-surface border-r border-border flex flex-col z-40">
      <div className="px-5 py-5 border-b border-border">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <Activity className="w-4 h-4 text-bg-primary" />
          </div>
          <span className="font-semibold text-text-primary text-base">
            HyperPulse
          </span>
        </Link>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors relative",
                active
                  ? "text-accent bg-accent/5"
                  : "text-text-muted hover:text-text-primary hover:bg-bg-elevated",
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-r" />
              )}
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          );
        })}

        <div className="pt-4 mt-4 border-t border-border">
          <p className="px-3 mb-2 text-xs text-text-dim uppercase tracking-wider">
            More
          </p>
          {SECONDARY_ITEMS.map(({ href, label, icon: Icon, disabled }) => (
            <span
              key={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium",
                disabled
                  ? "text-text-dim cursor-not-allowed opacity-50"
                  : "text-text-muted",
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </span>
          ))}
        </div>
      </nav>

      <div className="px-4 py-4 border-t border-border">
        <div className="rounded-lg bg-bg-elevated border border-border px-3 py-2.5">
          <p className="text-xs text-text-muted">Phase 2</p>
          <p className="text-xs text-accent mt-0.5">AI + rankings live</p>
        </div>
      </div>
    </aside>
  );
}
