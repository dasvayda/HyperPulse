# Storage retention and test recovery

Implemented 2026-11-25. PostgreSQL and SQLite share the same retention queries.

## Default policy

- Market snapshots: seven days; always preserve the latest timestamp/id per
  asset, including delisted assets. This covers 1h/4h trend and 15m resolution.
- Trader strategy inference: seven days plus the newest result per wallet.
- Resolved Pulse signals and paired results: rolling 30 days, matching the
  scorecard's maximum range. Unresolved signals remain for the resolver.
- Signal evidence: delete only unreferenced records older than seven days.
  All `brief_sessions`, `alerts`, current `market_briefs`, and retained
  `pulse_signals` protect their evidence. Nullable IDs cannot poison the query.
- Never automatically delete published editions, notes, alerts, traders,
  verified liquidation provenance, or any `paper_*` accounting records.
- Existing whale-flow retention (48h) and legacy Pulse count limit still apply.

An hourly worker runs separately from collection, off the event loop. It starts
when background tasks start, including with collectors disabled. Each table gets
at most 20 batches of 500 rows per run. Transactions commit per batch; PostgreSQL
uses a transaction advisory lock, 1s lock timeout and 10s statement timeout.
Failure is logged and retried at the next interval. There is no VACUUM FULL,
TRUNCATE, schema migration, or long blocking startup maintenance in this worker.
`RETENTION_ENABLED=false` disables it. Days below seven are clamped to seven.
Pulse retention is at least the hot retention period.

New evidence bodies use lossless zlib/base64 only when smaller than original
JSON. The evidence ID and digest still refer to original JSON; retrieval checks
the decompressed digest. Existing uncompressed bodies remain readable. Rollback
to code predating this storage codec requires decoding compressed bodies first.
Coin brief GETs reuse a copied result for 60s in a maximum 64-entry cache; force
refresh still works. Its `as_of` remains the actual cached observation time.

## Operator diagnostics / maintenance

Run from backend with the intended DATABASE_URL, without printing its value:

```powershell
python -m scripts.maintain_storage
python -m scripts.maintain_storage --apply
```

Default is read-only: PostgreSQL table/index sizes, estimated live/dead rows,
database size, and exact eligible counts. Preview counts may be expensive on a
large SQLite DB. `--apply` is one bounded retention pass, not an unbounded purge.
The report does not include filesystem/WAL size; inspect volume usage and WAL
separately if relation sizes do not explain disk usage. Retention is not a hard
disk quota: reference-protected publications/accounting still grow. Monitor
usage and run frequency against actual ingestion rate.

## Emergency transient reset (test environment only)

A newly deployed, full DB may have no rows older than seven days. Normal
retention cannot recover that space. Stop ALL API/collector workers first,
including any worker sharing the database, then inspect sizes and preview:

```powershell
python -m scripts.maintain_storage --reset-transient
python -m scripts.maintain_storage --reset-transient --apply
```

The reset discards ALL market snapshots, trader inferences, Pulse signals and
results (including recent observations). On PostgreSQL it locks durable
reference tables, keeps their evidence in memory (maximum 64 MiB, aborts before
truncation if exceeded), truncates transient and evidence tables, and restores
protected evidence in the same transaction. This frees table/index/TOAST files
without VACUUM FULL's rewrite space. It does not manually touch pg_wal, and cannot
fix a retained WAL/replication-slot problem. Published editions, alert history,
their evidence, and paper accounting remain intact. SQLite uses deletes and
does not automatically shrink its file. No full-database reset is automatic.

Restart the API/collectors to clear in-memory caches, verify DB writes and volume
usage, and allow at least 4h to rebuild trend history. Historical Pulse results
are lost. Paper balances survive, but forward decisions can pause/wait until
inputs are available. Saved paper decisions contain original observations;
arbitrary raw-history replays are no longer possible after snapshot expiry.

Do not run DELETE/VACUUM FULL against a full volume expecting immediate relief.
Regular DELETE primarily makes pages reusable after vacuum; autovacuum should
remain enabled. WAL and failed-write retry traffic need separate diagnosis.

## Verification

`tests/test_retention.py` exercises cutoff boundaries, delisted asset preservation,
latest inference preservation, every evidence reference, pending/resolved Pulse
lifecycle, batch limits, lossless legacy/compressed retrieval and corruption,
coin GET reuse, and transient reset preserving durable records. Tests use a
temporary SQLite DB and isolated PostgreSQL schemas when
`RETENTION_TEST_POSTGRES_URL` is supplied. PostgreSQL CI runs both variants.
