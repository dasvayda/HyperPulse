# HyperPulse Deployment Runbook

This runbook is for the Docker production-like stack in
`docker-compose.prod.yml`. It is deliberately source-ref based: the current
compose file builds containers from the checked-out Git revision, not from
versioned registry images.

## Before deploying

1. Pick the exact Git commit to deploy. Do not deploy an uncommitted working
   tree.
2. Create `.env` from `.env.example` on the host. Set a strong
   `POSTGRES_PASSWORD`, the exact public frontend origin in `CORS_ORIGINS`, and
   production values for `ENVIRONMENT=production`, `PIPELINE_RUN_TOKEN`,
   `API_DOCS_ENABLED=false`, and `CORS_ALLOW_CREDENTIALS=false`. Optionally set
   `PUBLIC_APP_URL` for Telegram deep links. Production compose passes these
   values into the backend and fails closed for the manual pipeline endpoint if
   its token is absent.
3. Add Telegram and AI provider credentials only in the host `.env`; never
   paste them into a terminal transcript, issue, or commit.
4. Confirm a recoverable database backup exists before changing code. The
   command below writes a dated SQL dump on the deployment host:

   ```bash
   docker compose -f docker-compose.prod.yml exec -T postgres \
     sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
     > "hyperpulse-$(date +%F-%H%M).sql"
   ```

   A successful command is not a restore test. Backup/restore validation
   remains a separate launch requirement.

## Deploy

From a clean checkout at the chosen commit:

```bash
git fetch origin
git status --short
git rev-parse --short HEAD
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml ps
```

Wait until `postgres`, `redis`, `backend`, and `frontend` report healthy. Then
run read-only smoke checks. `health/ready` may report Redis as `fallback` when
the application has intentionally switched to memory cache, but the database
and collector must be `ok` before declaring the deploy ready.

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:8000/api/v2/pipeline/status
curl -fsS http://127.0.0.1:8000/api/v2/alerts/summary
curl -fI http://127.0.0.1:3000/
```

Do not call `POST /api/v2/pipeline/run` as a deployment smoke test: it can
generate real alert candidates. Instead, watch the normal scheduled collector
cycle and confirm the collector timestamp advances.

## Roll back application code

Use this only when the checkout has no uncommitted changes and the previous
known-good commit is recorded. The current stack has no Alembic migration
workflow, so application releases must not include destructive schema changes
until migration and restore procedures are introduced.

```bash
git status --short
git switch --detach <known-good-commit>
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8000/health/ready
```

After recovery, record the failed revision, the known-good revision, the
readiness output, and whether any Telegram deliveries failed. Return to the
normal branch only after the incident is understood:

```bash
git switch main
```

## Incident quick checks

Run a read-only operator check from `backend/`:

```bash
python -m app.ops_check --base-url http://127.0.0.1:8100
# Production compose uses port 8000:
python -m app.ops_check --base-url http://127.0.0.1:8000 --timeout 5 --max-stage-age 600
```

The command makes only four GET requests (liveness, readiness, pipeline status,
Telegram summary), with finite per-request timeouts and no redirects. It does
not import application settings/DB, start collectors, send Telegram messages,
or call the manual pipeline endpoint. Output is JSON without raw provider
errors or response bodies. Exit codes are **0 healthy, 1 warning, 2 critical**.
An old backend without `stages` is critical, not silently treated as healthy.
Use 600s for normal stage freshness; trader refresh allows 1800s because its
configured default cadence is 900s. Adjust thresholds if scheduler intervals
change. Never put credentials in the base URL.

Daily/on-incident response:

1. Exit 2: check readiness and component logs first. A live process is not proof
   the API is listening or that data is fresh. Check the actual configured port.
2. `collector_degraded` with `liquidations`: expected until a verified source is
   approved. Keep Paper Portfolio paused; do not bypass the guard to obtain green.
3. DB failure: preserve data, verify connectivity, use the documented recovery
   procedure. Do not delete/recreate the DB as an automated repair.
4. Redis fallback: service can still run on single-process memory; inspect Redis
   and confirm reconnection. Do not interpret cache recovery as DB recovery.
5. Telegram warnings refer to recent 24h history, not proof of a current outage.
   Check recent failed/queued records and bot permissions without sharing tokens.
6. Stuck/stale stage: collect stage times and sanitized logs before deciding on
   a restart. Recheck after recovery and retain the incident timestamp/revision.

This check can be used by a host monitor, but no recurring job or notification
destination is provisioned here. An independent uptime/incident alert channel
still needs an operator decision and deployment setup.

`GET /api/v2/pipeline/status` includes `stages` for collector, trader refresh,
inference, ranking and alert processing. Each reports `never_run`, `running`,
`ok`, `degraded`, `error` or `cancelled`, with timestamps, duration in milliseconds,
and consecutive failure count. Error types are public; exception messages are not.
The stage's `last_success_at` is preserved on failure. A completed alert cycle
with no candidates is `ok`; this is **not** a successful Telegram delivery. Use
`/api/v2/alerts/summary` for delivery outcomes. New queued/failed deliveries,
including retries, mark the alert cycle degraded. All stage state is process-local
and resets on restart; it is not a persistent uptime or multi-worker aggregate.

Redis failure switches cache reads/writes to process memory with the same TTL.
Connection and command timeouts are 2 seconds; reconnect is attempted after
60 seconds when a cache operation or readiness check runs. On recovery Redis
becomes authoritative and fallback entries are discarded rather than replayed.
Memory entries do not survive a backend restart and are not shared between
workers. DB-backed records remain separate from this disposable cache.
`/health/ready` reports `cache.status=fallback` during an outage.

- `docker compose -f docker-compose.prod.yml logs --tail=200 backend`
- `docker compose -f docker-compose.prod.yml logs --tail=200 frontend`
- `docker compose -f docker-compose.prod.yml logs --tail=200 postgres redis`
- `curl -fsS http://127.0.0.1:8000/health/ready`
- `curl -fsS http://127.0.0.1:8000/api/v2/alerts/summary`

Never include `.env` contents, Authorization headers, Telegram bot tokens, or
AI API keys in incident logs.

## Logging safeguards (2026-10-29)

Application startup installs a redacting formatter on existing root and Uvicorn
handlers. It sanitizes the final output, including exception tracebacks:
configured AI/Telegram/operations keys, DB/Redis passwords, credential-bearing
DSNs, Telegram bot URLs, Bearer/Basic credentials, and common secret assignments.
Provider status and non-sensitive timing context remain visible. Custom handlers
installed later must also use `app.logging_config.SecretRedactingFormatter`.

This is defence in depth, not permission to log request bodies, settings, `.env`,
or provider responses. A separate audit of host log exporters, retention, and
public error pages is still required. If a secret is exposed, restrict the log,
rotate the affected credential, and record the incident without copying it.
