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
