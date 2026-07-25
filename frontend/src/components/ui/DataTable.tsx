import clsx from "clsx";
import type React from "react";

interface DataTableProps {
  children: React.ReactNode;
  className?: string;
}

export function DataTable({ children, className }: DataTableProps) {
  return (
    <div
      className={clsx(
        "overflow-x-auto rounded-xl border border-border bg-bg-surface",
        className,
      )}
    >
      <table className="w-full text-sm">{children}</table>
    </div>
  );
}

export function DataTableHead({ children }: { children: React.ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-border text-left text-xs text-text-muted">
        {children}
      </tr>
    </thead>
  );
}

export function DataTableHeaderCell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th className={clsx("px-4 py-3 font-medium whitespace-nowrap", className)}>
      {children}
    </th>
  );
}

export function DataTableBody({ children }: { children: React.ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function DataTableRow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <tr
      className={clsx(
        "border-b border-border-subtle transition-colors hover:bg-bg-elevated/50 last:border-0",
        className,
      )}
    >
      {children}
    </tr>
  );
}

export function DataTableCell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <td className={clsx("px-4 py-3.5 whitespace-nowrap", className)}>
      {children}
    </td>
  );
}

interface StatCardProps {
  label: React.ReactNode;
  value: string;
  change?: string;
  positive?: boolean;
  /** Optional Longs / Shorts style breakdown under the value. */
  details?: { label: string; value: string; tone?: "positive" | "negative" | "muted" }[];
}

export function StatCard({ label, value, change, positive, details }: StatCardProps) {
  return (
    <div className="rounded-xl border border-border bg-bg-surface p-5">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <p className="text-2xl font-semibold text-text-primary">{value}</p>
      {details && details.length > 0 && (
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5">
          {details.map((row) => (
            <span
              key={row.label}
              className={clsx(
                "text-xs font-medium",
                row.tone === "positive" && "text-positive",
                row.tone === "negative" && "text-negative",
                (row.tone === "muted" || row.tone == null) && "text-text-muted",
              )}
            >
              {row.label} {row.value}
            </span>
          ))}
        </div>
      )}
      {change && (
        <p
          className={clsx(
            "text-xs mt-1 font-medium",
            positive === undefined
              ? "text-text-muted"
              : positive
                ? "text-positive"
                : "text-negative",
          )}
        >
          {change}
        </p>
      )}
    </div>
  );
}

interface PageHeaderProps {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
          {title}
          <span className="text-text-dim cursor-help text-base">ⓘ</span>
        </h1>
        {description && (
          <p className="text-sm text-text-muted mt-1">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

interface AssetIconProps {
  asset: string;
}

const ASSET_COLORS: Record<string, string> = {
  BTC: "bg-orange-500",
  ETH: "bg-indigo-500",
  SOL: "bg-purple-500",
  HYPE: "bg-accent",
};

export function AssetIcon({ asset }: AssetIconProps) {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className={clsx(
          "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-bg-primary",
          ASSET_COLORS[asset] ?? "bg-text-muted",
        )}
      >
        {asset.slice(0, 1)}
      </div>
      <span className="font-medium text-text-primary">{asset}</span>
    </div>
  );
}

export function TrendValue({
  value,
  pct,
}: {
  value: string;
  pct?: number;
}) {
  const isPositive = pct !== undefined && pct >= 0;
  return (
    <div className="flex flex-col">
      <span className="font-medium text-text-primary">{value}</span>
      {pct !== undefined && (
        <span
          className={clsx(
            "text-xs font-medium",
            isPositive ? "text-positive" : "text-negative",
          )}
        >
          {isPositive ? "+" : ""}
          {pct.toFixed(1)}%
        </span>
      )}
    </div>
  );
}
