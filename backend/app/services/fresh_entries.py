"""BL-01: fresh whale entry window (24h)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.schemas import AlertType, WhaleAlert

FRESH_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def classify_size_change(
    prev: float,
    size: float,
    prev_usd: float,
    usd_size: float,
    min_add_usd: float,
) -> tuple[AlertType | None, float | None]:
    """Map coin-size change to ENTRY/EXIT plus USD delta.

    Same-side size-ups emit ENTRY when the USD add is at least min_add_usd.
    """
    if abs(prev) < 1e-6 and abs(size) >= 1e-6:
        return AlertType.ENTRY, round(usd_size, 2)
    if abs(prev) >= 1e-6 and abs(size) < 1e-6:
        return AlertType.EXIT, -round(abs(prev_usd or usd_size), 2)
    if prev * size < 0:
        return AlertType.ENTRY, round(usd_size, 2)
    if prev * size > 0 and abs(size) > abs(prev):
        delta = usd_size - abs(prev_usd)
        if delta >= min_add_usd:
            return AlertType.ENTRY, round(delta, 2)
    return None, None


def is_fresh_entry(alert: WhaleAlert, now: datetime | None = None) -> bool:
    if alert.alert_type.value != "entry":
        return False
    now = now or _utcnow()
    try:
        return _aware(alert.timestamp) >= now - timedelta(hours=FRESH_HOURS)
    except TypeError:
        return False
