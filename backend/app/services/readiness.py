"""Production readiness checks separate from the lightweight liveness endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.models.schemas import ReadinessComponent, ReadinessStatus
from app.services.cache import cache_backend_status
from app.services.store import store


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def collector_readiness(
    last_collect_at: datetime | None,
    *,
    now: datetime | None = None,
) -> ReadinessComponent:
    checked_at = now or _utcnow()
    if not settings.collector_enabled:
        return ReadinessComponent(
            status="disabled",
            detail="Collector is disabled by configuration",
            checked_at=checked_at,
        )
    if last_collect_at is None:
        return ReadinessComponent(
            status="starting",
            detail="No successful collector cycle recorded yet",
            checked_at=checked_at,
        )

    last_success_at = last_collect_at
    if last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=timezone.utc)
    max_age_seconds = max(settings.collector_interval_seconds * 3, 180)
    age_seconds = (checked_at - last_success_at).total_seconds()
    if age_seconds > max_age_seconds:
        return ReadinessComponent(
            status="stale",
            detail=f"Last successful collection was {int(age_seconds)}s ago",
            checked_at=checked_at,
            last_success_at=last_success_at,
        )
    return ReadinessComponent(
        status="ok",
        detail=f"Last successful collection was {int(max(age_seconds, 0))}s ago",
        checked_at=checked_at,
        last_success_at=last_success_at,
    )


def database_readiness(*, now: datetime | None = None) -> ReadinessComponent:
    checked_at = now or _utcnow()
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        return ReadinessComponent(
            status="error",
            detail="Database query failed",
            checked_at=checked_at,
        )
    return ReadinessComponent(status="ok", detail="Database query succeeded", checked_at=checked_at)


def cache_readiness(*, now: datetime | None = None) -> ReadinessComponent:
    checked_at = now or _utcnow()
    state, detail = cache_backend_status()
    return ReadinessComponent(status=state, detail=detail, checked_at=checked_at)


def get_readiness(*, now: datetime | None = None) -> ReadinessStatus:
    checked_at = now or _utcnow()
    database = database_readiness(now=checked_at)
    cache = cache_readiness(now=checked_at)
    collector = collector_readiness(store.last_collect_at, now=checked_at)
    ready = database.status == "ok" and collector.status == "ok"
    return ReadinessStatus(
        status="ready" if ready else "degraded",
        database=database,
        cache=cache,
        collector=collector,
    )
