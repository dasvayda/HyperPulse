"""Wallet-scoped evidence only. Never feeds market-wide liquidation rules."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db import SessionLocal
from app.models.orm import LiquidationCoverageRow, LiquidationQuarantineRow, VerifiedLiquidationRow


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def watch_addresses() -> list[str]:
    addresses = list(dict.fromkeys(x.strip().lower() for x in settings.liquidation_watch_addresses.split(",") if x.strip()))
    if not addresses or any(not re.fullmatch(r"0x[0-9a-f]{40}", x) for x in addresses):
        raise ValueError("Configure valid liquidation watch addresses")
    if settings.liquidation_other_ws_users < 0 or len(addresses) + settings.liquidation_other_ws_users > 10:
        raise ValueError("User-specific WebSocket budget exceeds 10 addresses")
    return addresses


def normalize_fill(wallet: str, fill: dict, *, received_at: datetime | None = None) -> dict | None:
    """Reject ambiguous participant/position direction instead of guessing."""
    received_at = received_at or utcnow()
    marker = fill.get("liquidation")
    if not isinstance(marker, dict) or str(marker.get("liquidatedUser", "")).lower() != wallet.lower():
        return None
    if marker.get("method") not in {"market", "backstop"}:
        return None
    try:
        if any(isinstance(v, bool) for v in (fill["px"], fill["sz"], fill["startPosition"], marker["markPx"])):
            return None
        price, size, start, mark = (float(fill["px"]), float(fill["sz"]), float(fill["startPosition"]), float(marker["markPx"]))
        if not all(math.isfinite(v) for v in (price, size, start, mark)) or min(price, size, mark) <= 0 or start == 0:
            return None
        side = "long" if start > 0 else "short"
        if fill.get("side") != ("A" if start > 0 else "B") or size > abs(start) * (1 + 1e-9):
            return None
        ts = fill["time"]
        tid = fill["tid"]
        if isinstance(ts, bool) or not isinstance(ts, int) or not isinstance(tid, int) or isinstance(tid, bool) or tid < 0:
            return None
        event_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        if ts <= 0 or event_at > received_at + timedelta(seconds=30):
            return None
        if not isinstance(fill.get("coin"), str) or not fill["coin"] or not re.fullmatch(r"0x[0-9a-fA-F]{64}", str(fill.get("hash", ""))):
            return None
        notional = price * size
        if not math.isfinite(notional):
            return None
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        return None
    key = f"{settings.hyperliquid_ws_url}|{wallet.lower()}|{fill['coin']}|{ts}|{tid}"
    return dict(id=hashlib.sha256(key.encode()).hexdigest(), wallet=wallet.lower(), asset=fill["coin"],
                side=side, price=price, size_usd=notional, event_at=event_at, received_at=received_at,
                raw_json=json.dumps({"schema_version": 1, "source": "hyperliquid.userFills", "fill": fill}, allow_nan=False))


def ingest(wallet: str, fills: list[dict]) -> tuple[int, int]:
    accepted = rejected = 0
    with SessionLocal() as db:
        for fill in fills:
            if not isinstance(fill, dict):
                rejected += 1
                continue
            if "liquidation" not in fill:
                continue
            row = normalize_fill(wallet, fill)
            if row is None:
                rejected += 1
                # Only the userFills payload is persisted; no connection headers.
                raw = json.dumps(fill, sort_keys=True, default=str)
                key = hashlib.sha256((wallet + raw).encode()).hexdigest()
                if not db.get(LiquidationQuarantineRow, key):
                    db.add(LiquidationQuarantineRow(id=key, wallet=wallet, raw_json=raw))
                    db.flush()
            elif not db.get(VerifiedLiquidationRow, row["id"]):
                db.add(VerifiedLiquidationRow(**row))
                db.flush()
                accepted += 1
        db.commit()
    return accepted, rejected


def coverage_start(roster: list[str]) -> str:
    from uuid import uuid4
    now = utcnow()
    with SessionLocal() as db:
        # Crash/restart intervals are never silently joined to a new stream.
        for old in db.query(LiquidationCoverageRow).filter(LiquidationCoverageRow.ended_at.is_(None)):
            old.ended_at = old.last_seen_at
            old.reason = "restart_gap"
        key = uuid4().hex
        db.add(LiquidationCoverageRow(id=key, roster_json=json.dumps(roster), started_at=now, last_seen_at=now))
        db.commit()
    return key


def coverage_touch(key: str, *, end: str | None = None):
    with SessionLocal() as db:
        row = db.get(LiquidationCoverageRow, key)
        if row:
            # On disconnect, completeness stops at the last confirmed heartbeat.
            if end:
                row.ended_at = row.last_seen_at
                row.reason = end
            else:
                row.last_seen_at = utcnow()
            db.commit()


def summary(hours: int = 1) -> dict:
    now = utcnow()
    cutoff = now - timedelta(hours=hours)
    try:
        roster = watch_addresses() if settings.verified_liquidations_enabled else []
    except ValueError:
        roster = []
    with SessionLocal() as db:
        intervals = db.query(LiquidationCoverageRow).filter(LiquidationCoverageRow.last_seen_at >= cutoff).order_by(LiquidationCoverageRow.started_at).all()
        cursor = cutoff
        for row in intervals:
            if json.loads(row.roster_json) != roster:
                continue
            start, end = aware(row.started_at), aware(row.last_seen_at)
            if start <= cursor:
                cursor = max(cursor, end)
        complete = bool(roster) and cursor >= now - timedelta(seconds=30)
        rows = db.query(VerifiedLiquidationRow).filter(VerifiedLiquidationRow.event_at >= cutoff, VerifiedLiquidationRow.event_at <= now).all()
        rows = [r for r in rows if r.wallet in roster]
        observed_long = sum(r.size_usd for r in rows if r.side == "long")
        observed_short = sum(r.size_usd for r in rows if r.side == "short")
        active = any(r.ended_at is None and aware(r.last_seen_at) >= now - timedelta(seconds=30) and json.loads(r.roster_json) == roster for r in intervals)
        return {"source": "hyperliquid.userFills", "scope": "watched_wallets", "status": "ok" if complete else "partial" if active else "unavailable",
                "wallets": roster, "window_hours": hours, "as_of": now.isoformat(), "gap": not complete,
                "long_usd": observed_long if complete else None, "short_usd": observed_short if complete else None,
                "observed_long_usd": observed_long, "observed_short_usd": observed_short,
                "events": len(rows), "market_coverage": "unavailable", "paper_compatible": False,
                "recent_events": [{"id": r.id, "wallet": r.wallet, "asset": r.asset, "side": r.side,
                                   "price": r.price, "size_usd": r.size_usd, "event_at": aware(r.event_at).isoformat(),
                                   "received_at": aware(r.received_at).isoformat(),
                                   "source": "hyperliquid.userFills", "fill": json.loads(r.raw_json)["fill"]}
                                  for r in sorted(rows, key=lambda r: r.event_at, reverse=True)[:50]],
                "intervals": [{"started_at": aware(r.started_at).isoformat(), "last_seen_at": aware(r.last_seen_at).isoformat(),
                               "ended_at": aware(r.ended_at).isoformat() if r.ended_at else None, "reason": r.reason} for r in intervals]}
