# Home navigation and database storage — 2026-10-10

## Verified cause

During the incident all five probed APIs, including `/health`, timed out after
12 seconds. Two live stack samples showed the main asyncio thread inside
`_ranking_cycle -> run_ranking_pipeline -> summarize_open_pnl -> _latest_mark_prices`.
SQLite contained approximately 1.81 million market snapshots (234 assets),
758,000 legacy liquidation rows and 73,000 inference rows; file size was about
1 GB. The latest-mark query used an asset index but a temporary sort.

## Changes

- Share live collector prices across an entire ranking/enrichment calculation.
  Missing assets use indexed DB lookups once per calculation, not per wallet.
- Offload ranking, ranking enrichment, paper decisions, Pulse resolution and
  rule-insight construction from the API event loop to worker threads.
- Add `(asset, timestamp)` and `timestamp` indexes, including existing SQLite
  database migration. Indexes improve lookup speed, not file size.
- Home streams its optional Market Brief and CMC cards separately. API calls
  have a ten-second timeout; navigation has loading and retry/error UI.
- Preserve `.next` unless `HP_CLEAR_NEXT_CACHE=1` is explicitly requested.
- The freshness badge reads a same-origin status route. The local `.env` CORS
  allowlist still referenced port 3000 while the frontend uses 3100; this caused
  a false "status unavailable" badge despite healthy server-side API requests.
  No credentials or environment configuration are exposed or changed.
- `start_backend.ps1` now also saves console output to `logs/backend-live.log`.
  Pipeline initialization is not advertised as HTTP readiness.

## Storage policy and safe maintenance

Keep at least seven days of high-resolution market snapshots in the hot DB.
Keep each asset's latest observation even if it is older. Long-term market
history is moved losslessly to a separate SQLite archive; it is not a product
feature and is not queried by live ranking. Hourly aggregate storage is a
possible later optimization, not implemented in this change.

Do not delete Paper Portfolio trades, decisions, NAV, roster or alert evidence.
Do not use old unverified liquidation rows as market truth. They remain intact
until their provenance is audited. This utility only handles market snapshots.

From `backend/`, first preview (read-only, does not create an archive):

```powershell
.venv/Scripts/python.exe scripts/archive_market_snapshots.py --days 7
```

For maintenance: stop the backend, use a new backup path with enough free
space, then explicitly apply. The CLI creates a consistent full backup first,
commits archive copies before verifying every column and deleting the copied
hot rows. It rejects mismatches and reuse with another source DB. Repeat runs
are idempotent. Do not run a source-swapping migration concurrently with it.

```powershell
.venv/Scripts/python.exe scripts/archive_market_snapshots.py --days 7 --apply --backup hyperpulse-before-archive.db --archive market-history.db
```

Deletion frees pages for reuse but does not necessarily shrink the SQLite file.
Only compact after a verified backup, while the backend is stopped; reserve
space for temporary files. Never run VACUUM on every collector cycle.
No automatic retention deletion or VACUUM runs during server startup.

## Verification results

- 109 backend regression tests passed, including worker/event-loop isolation,
  shared prices, SQLite migration/query plan, archive preview, lossless batched
  transfer, repeat runs and conflict protection. Tests use a separate DB.
- Frontend production build and TypeScript validation passed.
- Existing local DB received indexes without deleting rows. Indexed BTC latest
  lookup repeated 100 times took 0.036s; live ranking cycles took 0.16–0.58s.
- Five successive live `/health` probes returned 200 in 0.004–0.005s. Warm Home
  returned its first byte in 0.20s and completed in 0.65s. A cold development
  compilation was slower (5.38s to first byte); production builds avoid it.
- Archive preview identified 1,053,367 eligible snapshots. No archive transfer
  or VACUUM was applied to the original local DB. File size is not reduced yet.
- CMC returned 429 during validation; Home continued with an unavailable label.

After restart, verify both `/health` response latency and `/health/ready`.
The latter may intentionally remain degraded because verified liquidation
coverage is currently unavailable; that is separate from HTTP responsiveness.
