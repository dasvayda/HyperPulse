"""A bounded, versioned audit view. Directional accuracy is not trading P&L."""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import case, func

from app.db import SessionLocal
from app.models.orm import PulseResultRow, PulseSignalRow
from app.services.pulse import HORIZON_SEC, SCORECARD_ENGINE, _ensure_aware


def scorecard(asset: str | None, days: int, offset: int, limit: int, *, now=None, day: date | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since = datetime.combine(day, time.min, timezone.utc) if day else now - timedelta(days=days)
    until = min(now, datetime.combine(day, time.max, timezone.utc)) if day else now
    signal, result = PulseSignalRow, PulseResultRow
    outcome = case(
        (result.signal_id.is_(None), "pending"),
        (result.observed_at.is_(None), "unavailable"),
        (signal.direction == "wait", "wait"),
        (result.hit == 1, "hit"),
        else_="miss",
    )
    with SessionLocal() as db:
        query = (db.query(signal, result).outerjoin(result, signal.id == result.signal_id)
                 .filter(signal.engine == SCORECARD_ENGINE, signal.horizon_sec == HORIZON_SEC,
                         signal.evidence_id.is_not(None), signal.created_at >= since, signal.created_at <= until))
        if asset:
            query = query.filter(signal.asset == asset)
        counts = dict.fromkeys(("hit", "miss", "wait", "pending", "unavailable"), 0)
        counts.update(dict(query.with_entities(outcome, func.count()).group_by(outcome).all()))
        rows = query.order_by(signal.created_at.desc(), signal.id.desc()).offset(offset).limit(limit).all()
        items = []
        for sig, res in rows:
            created = _ensure_aware(sig.created_at)
            observed = _ensure_aware(res.observed_at) if res and res.observed_at else None
            status = ("pending" if res is None else "unavailable" if observed is None
                      else "wait" if sig.direction == "wait" else "hit" if res.hit else "miss")
            items.append({
                "id": sig.id, "asset": sig.asset, "direction": sig.direction, "status": status,
                "as_of": created, "due_at": created + timedelta(seconds=HORIZON_SEC),
                "observed_at": observed, "baseline_mark": sig.mark_at_emit,
                "result_mark": res.mark_at_resolve if observed else None,
                "evidence_id": sig.evidence_id,
            })
    return {"engine": SCORECARD_ENGINE, "since": since, "as_of": now, "counts": counts,
            "directional_evaluated": counts["hit"] + counts["miss"],
            "total": sum(counts.values()), "offset": offset, "items": items}
