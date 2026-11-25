"""Bounded hot-data retention. Never deletes published editions or paper accounts.

Works on SQLite and PostgreSQL. No VACUUM FULL, TRUNCATE, or schema changes.
Every batch commits separately; rerunning after failure is safe.
"""
from datetime import datetime, timedelta, timezone
import logging
import threading

from sqlalchemy import exists, or_, select, union
from sqlalchemy.orm import aliased

from app.config import settings
from app.db import SessionLocal
from app.models.orm import (
    AlertRow, BriefSessionRow, EvidenceRow, InferenceRow, MarketBriefRow,
    MarketSnapshotRow, PulseResultRow, PulseSignalRow,
)

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def candidates(db, cutoff):
    """Lazy queries; selecting candidate IDs does not load JSON bodies."""
    newer = aliased(MarketSnapshotRow)
    snapshots = db.query(MarketSnapshotRow.id).filter(
        MarketSnapshotRow.timestamp < cutoff,
        exists(select(newer.id).where(
            newer.asset == MarketSnapshotRow.asset,
            or_(newer.timestamp > MarketSnapshotRow.timestamp,
                (newer.timestamp == MarketSnapshotRow.timestamp) & (newer.id > MarketSnapshotRow.id)),
        )),
    )
    newer_inference = aliased(InferenceRow)
    inferences = db.query(InferenceRow.id).filter(
        InferenceRow.created_at < cutoff,
        exists(select(newer_inference.id).where(
            newer_inference.trader_address == InferenceRow.trader_address,
            or_(newer_inference.created_at > InferenceRow.created_at,
                (newer_inference.created_at == InferenceRow.created_at) & (newer_inference.id > InferenceRow.id)),
        )),
    )
    # Keep unresolved observations; they may still be needed by the resolver.
    pulse_cutoff = cutoff - timedelta(days=max(0, settings.retention_pulse_days - max(7, settings.retention_days)))
    pulses = db.query(PulseSignalRow.id).filter(
        PulseSignalRow.created_at < pulse_cutoff,
        exists(select(PulseResultRow.signal_id).where(PulseResultRow.signal_id == PulseSignalRow.id)),
    )
    references = union(*[
        select(model.evidence_id).where(model.evidence_id.is_not(None))
        for model in (AlertRow, BriefSessionRow, MarketBriefRow, PulseSignalRow)
    ])
    evidence = db.query(EvidenceRow.id).filter(
        EvidenceRow.created_at < cutoff, EvidenceRow.id.not_in(references),
    )
    return {
        "market_snapshots": (MarketSnapshotRow, snapshots),
        "inference_results": (InferenceRow, inferences),
        "pulse_signals": (PulseSignalRow, pulses),
        "signal_evidence": (EvidenceRow, evidence),
    }


def run_retention(*, now=None, apply=True, session_factory=SessionLocal):
    """At most batch_size × max_batches deletions per table per hourly run.

    Preview counts all eligible rows (operator-only); apply never counts/scans
    full tables in Python. PostgreSQL transaction lock prevents overlapping jobs.
    """
    if not _lock.acquire(blocking=False):
        return {"skipped": "already_running"}
    try:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=max(7, settings.retention_days))
        batch_size = max(1, min(2000, settings.retention_batch_size))
        max_batches = max(1, min(100, settings.retention_max_batches))
        counts = {}
        with session_factory() as db:
            for name in ("market_snapshots", "inference_results", "pulse_signals", "signal_evidence"):
                counts[name] = 0
                for _ in range(max_batches if apply else 1):
                    if db.bind.dialect.name == "postgresql":
                        from sqlalchemy import text
                        db.execute(text("SET LOCAL lock_timeout = '1s'"))
                        db.execute(text("SET LOCAL statement_timeout = '10s'"))
                        if not db.execute(text("SELECT pg_try_advisory_xact_lock(72403017)")).scalar():
                            db.rollback()
                            return {**counts, "skipped": "already_running"}
                    model, query = candidates(db, cutoff)[name]
                    if not apply:
                        counts[name] = query.count()
                        db.rollback()
                        break
                    ids = [r[0] for r in query.order_by(model.id).limit(batch_size).all()]
                    if not ids:
                        db.rollback()
                        break
                    if model is PulseSignalRow:
                        db.query(PulseResultRow).filter(PulseResultRow.signal_id.in_(ids)).delete(synchronize_session=False)
                    deletion = db.query(model).filter(model.id.in_(ids))
                    if model is EvidenceRow:
                        # Re-check references in the DELETE statement as well as
                        # candidate selection (a publisher may have just run).
                        deletion = deletion.filter(model.id.in_(query.statement))
                    deleted = deletion.delete(synchronize_session=False)
                    db.commit()
                    counts[name] += deleted
                    if len(ids) < batch_size:
                        break
        logger.info("Retention %s cutoff=%s rows=%s", "apply" if apply else "preview", cutoff.isoformat(), counts)
        return counts
    finally:
        _lock.release()
