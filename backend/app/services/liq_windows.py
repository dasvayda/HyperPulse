"""BL-03: sampled liquidation USD rollups for 1h / 4h / 24h."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import SessionLocal
from app.models.orm import LiquidationRow
from app.services.store import store

WINDOWS_HOURS = (1, 4, 24)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(ts: datetime) -> datetime:
    if isinstance(ts, datetime) and ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _empty() -> dict[str, float | int]:
    return {"long_usd": 0.0, "short_usd": 0.0, "total_usd": 0.0, "events": 0}


def rollup_events(events: list[Any], hours: float, now: datetime | None = None) -> dict[str, float | int]:
    now = now or _utcnow()
    cutoff = now - timedelta(hours=hours)
    long_usd = 0.0
    short_usd = 0.0
    count = 0
    for event in events:
        ts = getattr(event, "timestamp", None)
        if not isinstance(ts, datetime):
            continue
        try:
            if _aware(ts) < cutoff:
                continue
        except TypeError:
            continue
        count += 1
        side = getattr(event, "side", None)
        side_val = side.value if hasattr(side, "value") else str(side or "")
        size = float(getattr(event, "size_usd", 0) or 0)
        if str(side_val).lower() == "long":
            long_usd += size
        else:
            short_usd += size
    return {
        "long_usd": round(long_usd, 2),
        "short_usd": round(short_usd, 2),
        "total_usd": round(long_usd + short_usd, 2),
        "events": count,
    }


def _rollup_db(hours: float, now: datetime) -> dict[str, float | int]:
    cutoff = now - timedelta(hours=hours)
    db = SessionLocal()
    try:
        rows = (
            db.query(LiquidationRow)
            .filter(LiquidationRow.timestamp >= cutoff)
            .all()
        )
        long_usd = 0.0
        short_usd = 0.0
        for row in rows:
            size = float(row.size_usd or 0)
            if (row.side or "").lower() == "long":
                long_usd += size
            else:
                short_usd += size
        return {
            "long_usd": round(long_usd, 2),
            "short_usd": round(short_usd, 2),
            "total_usd": round(long_usd + short_usd, 2),
            "events": len(rows),
        }
    except Exception:
        return _empty()
    finally:
        db.close()


def pressure_line(window: dict[str, float | int]) -> str:
    total = float(window.get("total_usd") or 0)
    long_usd = float(window.get("long_usd") or 0)
    short_usd = float(window.get("short_usd") or 0)
    if total <= 0:
        return "sampled liq quiet"
    if long_usd > short_usd * 1.5:
        return "long-flush pressure"
    if short_usd > long_usd * 1.5:
        return "short-flush pressure"
    return "no clean liq skew"


def rollup_liq_windows(now: datetime | None = None) -> dict[str, dict[str, float | int]]:
    now = now or _utcnow()
    out: dict[str, dict[str, float | int]] = {}
    mem = list(store.liquidation_events or [])
    for hours in WINDOWS_HOURS:
        key = f"{hours}h"
        rolled = rollup_events(mem, hours, now)
        db_rolled = _rollup_db(hours, now)
        if hours >= 4 and db_rolled["events"] >= rolled["events"]:
            rolled = db_rolled
        elif rolled["events"] == 0:
            rolled = db_rolled
        out[key] = rolled
    return out
