"""Short-horizon pulse signals (rules_v1).

Emit direction probabilities from the same whale/funding/liq votes used for
Prefer cards. Resolve against market_snapshots.mark_price after 15 minutes.
Pulse is separate from MarketInsight.confidence (rule-vote strength).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models.orm import MarketSnapshotRow, PulseResultRow, PulseSignalRow
from app.models.schemas import (
    InsightStance,
    PulseDirection,
    PulseSnapshot,
    PulseStatus,
    PulseTick,
)
from app.services.store import store

logger = logging.getLogger(__name__)

HORIZON_SEC = 900
EXPIRE_GRACE_SEC = 1200  # 20m — no snapshot after due → expired
FLAT_BPS = 5.0
KEEP_PER_ASSET = 48
TICK_LIMIT = 12
MIN_HIT_SAMPLES = 3
ENGINE = "rules_v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def probabilities_from_votes(
    votes: list[InsightStance],
    card_stance: InsightStance,
) -> tuple[PulseDirection, float, float, float]:
    """Map Prefer votes → calibrated-ish probs that sum to 1.

    HOLD / split → wait-heavy. If max direction conflicts with Prefer badge,
    tilt toward wait so the two surfaces do not fight.
    """
    if not votes:
        return PulseDirection.WAIT, 0.2, 0.2, 0.6

    n = len(votes)
    buy_n = sum(1 for v in votes if v == InsightStance.BUY)
    sell_n = sum(1 for v in votes if v == InsightStance.SELL)
    hold_n = n - buy_n - sell_n

    # Soft mass from vote counts; hold mass always contributes to wait.
    raw_up = buy_n / n
    raw_down = sell_n / n
    raw_wait = hold_n / n

    # When directional votes disagree, push residual into wait.
    if buy_n > 0 and sell_n > 0:
        conflict = min(buy_n, sell_n) / n
        raw_up = max(0.0, raw_up - conflict * 0.5)
        raw_down = max(0.0, raw_down - conflict * 0.5)
        raw_wait += conflict

    # Floor so bars stay visible.
    raw_up = max(0.05, raw_up)
    raw_down = max(0.05, raw_down)
    raw_wait = max(0.1, raw_wait)
    total = raw_up + raw_down + raw_wait
    p_up = raw_up / total
    p_down = raw_down / total
    p_wait = raw_wait / total

    direction = max(
        (
            (PulseDirection.UP, p_up),
            (PulseDirection.DOWN, p_down),
            (PulseDirection.WAIT, p_wait),
        ),
        key=lambda x: x[1],
    )[0]

    # Prefer badge conflict → tilt wait.
    prefer_dir = {
        InsightStance.BUY: PulseDirection.UP,
        InsightStance.SELL: PulseDirection.DOWN,
        InsightStance.HOLD: PulseDirection.WAIT,
    }[card_stance]
    if direction != PulseDirection.WAIT and prefer_dir != PulseDirection.WAIT and direction != prefer_dir:
        p_wait = min(0.7, p_wait + 0.25)
        leftover = 1.0 - p_wait
        other = p_up + p_down
        if other > 0:
            p_up = leftover * (p_up / other)
            p_down = leftover * (p_down / other)
        else:
            p_up = leftover * 0.5
            p_down = leftover * 0.5
        # Prefer badge and vote direction disagree — never keep a fighting call.
        direction = PulseDirection.WAIT

    # Renormalize floating error.
    s = p_up + p_down + p_wait
    p_up, p_down, p_wait = p_up / s, p_down / s, p_wait / s
    if direction != PulseDirection.WAIT:
        direction = max(
            (
                (PulseDirection.UP, p_up),
                (PulseDirection.DOWN, p_down),
                (PulseDirection.WAIT, p_wait),
            ),
            key=lambda x: x[1],
        )[0]
    return direction, round(p_up, 4), round(p_down, 4), round(p_wait, 4)


def emit_pulse_for_asset(
    *,
    asset: str,
    votes: list[InsightStance],
    card_stance: InsightStance,
    mark_price: float,
    now: datetime | None = None,
) -> PulseSignalRow | None:
    """Persist one pulse_signals row. Returns None if mark is invalid."""
    if mark_price <= 0:
        return None
    now = _ensure_aware(now or _utcnow())
    direction, p_up, p_down, p_wait = probabilities_from_votes(votes, card_stance)
    signal_id = store.new_id("pulse")
    row = PulseSignalRow(
        id=signal_id,
        asset=asset.upper(),
        horizon_sec=HORIZON_SEC,
        direction=direction.value,
        p_up=p_up,
        p_down=p_down,
        p_wait=p_wait,
        mark_at_emit=float(mark_price),
        vote_json=json.dumps([v.value for v in votes]),
        engine=ENGINE,
        created_at=now,
    )
    db = SessionLocal()
    try:
        db.add(row)
        db.commit()
        _prune_asset(db, asset.upper())
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row
    except Exception:
        db.rollback()
        logger.exception("Failed to emit pulse for %s", asset)
        return None
    finally:
        db.close()


def _prune_asset(db, asset: str) -> None:
    rows = (
        db.query(PulseSignalRow)
        .filter(PulseSignalRow.asset == asset)
        .order_by(PulseSignalRow.created_at.desc())
        .all()
    )
    if len(rows) <= KEEP_PER_ASSET:
        return
    drop_ids = [r.id for r in rows[KEEP_PER_ASSET:]]
    if drop_ids:
        db.query(PulseResultRow).filter(PulseResultRow.signal_id.in_(drop_ids)).delete(
            synchronize_session=False
        )
        db.query(PulseSignalRow).filter(PulseSignalRow.id.in_(drop_ids)).delete(
            synchronize_session=False
        )


def resolve_due_pulses(now: datetime | None = None) -> int:
    """Score open pulses whose horizon has elapsed. Returns resolve count."""
    now = _ensure_aware(now or _utcnow())
    db = SessionLocal()
    resolved = 0
    try:
        open_rows = (
            db.query(PulseSignalRow)
            .outerjoin(PulseResultRow, PulseSignalRow.id == PulseResultRow.signal_id)
            .filter(PulseResultRow.signal_id.is_(None))
            .all()
        )
        for sig in open_rows:
            created = _ensure_aware(sig.created_at)
            due = created + timedelta(seconds=sig.horizon_sec)
            if now < due:
                continue
            expire_at = created + timedelta(seconds=EXPIRE_GRACE_SEC)
            snap = (
                db.query(MarketSnapshotRow)
                .filter(
                    MarketSnapshotRow.asset == sig.asset,
                    MarketSnapshotRow.timestamp >= due,
                )
                .order_by(MarketSnapshotRow.timestamp.asc())
                .first()
            )
            if snap is None:
                if now >= expire_at:
                    db.add(
                        PulseResultRow(
                            signal_id=sig.id,
                            mark_at_resolve=None,
                            outcome="expired",
                            return_bps=None,
                            hit=None,
                            resolved_at=now,
                        )
                    )
                    resolved += 1
                continue

            mark = float(snap.mark_price)
            emit_mark = float(sig.mark_at_emit)
            if emit_mark <= 0:
                outcome = "expired"
                return_bps = None
                hit = None
            else:
                return_bps = (mark - emit_mark) / emit_mark * 10_000.0
                if abs(return_bps) < FLAT_BPS:
                    outcome = "flat"
                elif return_bps > 0:
                    outcome = "up"
                else:
                    outcome = "down"

                if sig.direction == "wait":
                    # Wait "hits" when price stayed flat (no strong move).
                    hit = 1 if outcome == "flat" else 0
                elif outcome == "flat":
                    hit = 0
                else:
                    hit = 1 if outcome == sig.direction else 0

            db.add(
                PulseResultRow(
                    signal_id=sig.id,
                    mark_at_resolve=mark if emit_mark > 0 else None,
                    outcome=outcome,
                    return_bps=round(return_bps, 2) if return_bps is not None else None,
                    hit=hit,
                    resolved_at=now,
                )
            )
            resolved += 1
        if resolved:
            db.commit()
        return resolved
    except Exception:
        db.rollback()
        logger.exception("resolve_due_pulses failed")
        return 0
    finally:
        db.close()


def get_pulse_snapshot(asset: str, now: datetime | None = None) -> PulseSnapshot | None:
    """Latest pulse view for an asset (for Evidence / Brief attach)."""
    asset = asset.upper()
    now = _ensure_aware(now or _utcnow())
    db = SessionLocal()
    try:
        latest = (
            db.query(PulseSignalRow)
            .filter(PulseSignalRow.asset == asset)
            .order_by(PulseSignalRow.created_at.desc())
            .first()
        )
        if latest is None:
            return None

        created = _ensure_aware(latest.created_at)
        due = created + timedelta(seconds=latest.horizon_sec)
        result = (
            db.query(PulseResultRow)
            .filter(PulseResultRow.signal_id == latest.id)
            .first()
        )
        if result is not None:
            status = PulseStatus.RESOLVED
        elif now > due + timedelta(seconds=EXPIRE_GRACE_SEC):
            status = PulseStatus.STALE
        else:
            status = PulseStatus.OPEN

        history = (
            db.query(PulseSignalRow, PulseResultRow)
            .outerjoin(PulseResultRow, PulseSignalRow.id == PulseResultRow.signal_id)
            .filter(PulseSignalRow.asset == asset)
            .order_by(PulseSignalRow.created_at.desc())
            .limit(TICK_LIMIT)
            .all()
        )
        ticks: list[PulseTick] = []
        hits: list[bool] = []
        for sig, res in history:
            hit_val: bool | None = None
            if res is not None and res.hit is not None:
                hit_val = bool(res.hit)
                hits.append(hit_val)
            ticks.append(
                PulseTick(
                    direction=PulseDirection(sig.direction),
                    hit=hit_val,
                    created_at=_ensure_aware(sig.created_at),
                )
            )

        hit_n = len(hits)
        warming = hit_n < MIN_HIT_SAMPLES
        hit_rate = (sum(1 for h in hits if h) / hit_n) if hit_n else None

        return PulseSnapshot(
            asset=asset,
            horizon_sec=latest.horizon_sec,
            direction=PulseDirection(latest.direction),
            p_up=latest.p_up,
            p_down=latest.p_down,
            p_wait=latest.p_wait,
            as_of=created,
            due_at=due,
            status=status,
            ticks=ticks,
            hit_rate=round(hit_rate, 3) if hit_rate is not None and not warming else None,
            hit_n=hit_n,
            warming_up=warming,
        )
    finally:
        db.close()


def attach_pulses_to_insights(insights: list) -> None:
    """Mutate MarketInsight list in place: set pulse for coin-stance cards."""
    cache: dict[str, PulseSnapshot | None] = {}
    for insight in insights:
        if not insight.asset:
            continue
        # Prefer attaching to whale-book Prefer cards (title pattern from BL-02).
        title = (insight.title or "").lower()
        if "whale book" not in title and ":" not in (insight.title or ""):
            # Still attach for any asset-scoped evidence card so UI can show pulse.
            pass
        asset = insight.asset.upper()
        if asset not in cache:
            cache[asset] = get_pulse_snapshot(asset)
        insight.pulse = cache[asset]


def brief_pulse_asset(preferred: str | None = None) -> str | None:
    """Asset for Brief pulse teaser: explicit coin tab, else largest whale-book Top3."""
    if preferred:
        return preferred.upper()
    summary = store.whale_summary
    if not summary or not summary.by_asset:
        # Fall back to any recent pulse asset.
        db = SessionLocal()
        try:
            row = (
                db.query(PulseSignalRow)
                .order_by(PulseSignalRow.created_at.desc())
                .first()
            )
            return row.asset if row else None
        finally:
            db.close()
    ranked = sorted(
        summary.by_asset.values(),
        key=lambda a: a.long_notional_usd + a.short_notional_usd,
        reverse=True,
    )
    return ranked[0].asset if ranked else None
