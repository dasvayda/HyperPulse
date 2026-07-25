"use client";

import { useState } from "react";
import Link from "next/link";
import {
  DataTable,
  DataTableBody,
  DataTableCell,
  DataTableHead,
  DataTableHeaderCell,
  DataTableRow,
} from "@/components/ui/DataTable";
import { Badge } from "@/components/ui/Badge";
import { formatConfidence } from "@/lib/api";
import type { StrategyInference } from "@/types";

const PREVIEW_COUNT = 8;

interface WhaleStyleTagsTableProps {
  inferences: StrategyInference[];
  providerLabel: string;
  lastRunLabel: string;
}

export function WhaleStyleTagsTable({
  inferences,
  providerLabel,
  lastRunLabel,
}: WhaleStyleTagsTableProps) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded
    ? inferences
    : inferences.slice(0, PREVIEW_COUNT);
  const remaining = Math.max(0, inferences.length - PREVIEW_COUNT);

  return (
    <section className="rounded-xl border border-border bg-bg-surface">
      <div className="p-4 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-base font-semibold text-text-primary">
            Whale style tags
          </h2>
          <p className="text-xs text-text-dim mt-1">
            Trader style labels (secondary to the market brief). Provider:{" "}
            {providerLabel} · last run {lastRunLabel}
          </p>
        </div>
        {inferences.length > 0 && (
          <p className="text-xs text-text-dim">
            Showing {visible.length} of {inferences.length}
          </p>
        )}
      </div>

      {inferences.length === 0 ? (
        <p className="px-4 pb-4 text-sm text-text-muted">
          No trader tags yet — wait for the next inference cycle.
        </p>
      ) : (
        <div className="px-4 pb-4">
          <DataTable>
            <DataTableHead>
              <DataTableHeaderCell>Trader</DataTableHeaderCell>
              <DataTableHeaderCell>Strategy</DataTableHeaderCell>
              <DataTableHeaderCell>Style</DataTableHeaderCell>
              <DataTableHeaderCell>Risk</DataTableHeaderCell>
              <DataTableHeaderCell>Confidence</DataTableHeaderCell>
              <DataTableHeaderCell>Provider</DataTableHeaderCell>
              <DataTableHeaderCell>Rationale</DataTableHeaderCell>
            </DataTableHead>
            <DataTableBody>
              {visible.map((item) => (
                <DataTableRow key={item.id}>
                  <DataTableCell>
                    <Link
                      href={`/traders/${encodeURIComponent(item.trader_address)}`}
                      className="text-accent hover:underline font-medium"
                    >
                      {item.trader_alias}
                    </Link>
                  </DataTableCell>
                  <DataTableCell>
                    <Badge variant="accent">{item.strategy}</Badge>
                  </DataTableCell>
                  <DataTableCell className="text-text-muted">
                    {item.trading_style}
                  </DataTableCell>
                  <DataTableCell>
                    <Badge
                      variant={
                        item.risk_profile === "Aggressive"
                          ? "short"
                          : item.risk_profile === "Conservative"
                            ? "long"
                            : "default"
                      }
                    >
                      {item.risk_profile}
                    </Badge>
                  </DataTableCell>
                  <DataTableCell>
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 rounded-full bg-bg-elevated overflow-hidden">
                        <div
                          className="h-full rounded-full bg-accent"
                          style={{ width: `${item.confidence}%` }}
                        />
                      </div>
                      <span className="text-xs text-text-muted">
                        {formatConfidence(item.confidence)}
                      </span>
                    </div>
                  </DataTableCell>
                  <DataTableCell className="text-text-muted text-xs">
                    {item.provider}
                  </DataTableCell>
                  <DataTableCell className="text-text-muted max-w-md whitespace-normal">
                    {item.rationale}
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>

          {remaining > 0 && (
            <div className="mt-3 flex justify-center">
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="text-xs font-medium text-accent hover:underline"
              >
                {expanded ? "Show less" : `Show more (${remaining})`}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
