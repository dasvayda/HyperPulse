"""Storage diagnostics and opt-in maintenance, using the configured DATABASE_URL.

python -m scripts.maintain_storage                 # sizes + retention preview
python -m scripts.maintain_storage --apply         # bounded retention pass
python -m scripts.maintain_storage --reset-transient --apply

Stop the backend before transient reset. It intentionally discards snapshots,
inferences, all Pulse evaluations and unreferenced evidence, including recent
ones. Published editions, alert evidence and paper accounting are preserved.
"""
import argparse
import json

from sqlalchemy import delete, select, text, union

from app.db import SessionLocal, engine
from app.models.orm import (
    AlertRow, BriefSessionRow, EvidenceRow, InferenceRow, MarketBriefRow,
    MarketSnapshotRow, PulseResultRow, PulseSignalRow,
)
from app.services.retention import run_retention


def storage_report():
    if engine.dialect.name != "postgresql":
        return {"dialect": engine.dialect.name}
    with engine.connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = '10s'"))
        tables = conn.execute(text("""
            SELECT relname AS table_name, pg_total_relation_size(relid) AS total_bytes,
                   pg_table_size(relid) AS table_bytes, pg_indexes_size(relid) AS index_bytes,
                   n_live_tup AS estimated_rows, n_dead_tup AS estimated_dead_rows
            FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC
        """)).mappings().all()
        return {"database_bytes": conn.execute(text("SELECT pg_database_size(current_database())")).scalar(),
                "tables": [dict(r) for r in tables]}


def reset_transient():
    """Maintenance window only. No CASCADE and no changes to paper_* tables."""
    with SessionLocal() as db:
        models = (PulseResultRow, PulseSignalRow, MarketSnapshotRow, InferenceRow)
        refs = union(*[select(m.evidence_id).where(m.evidence_id.is_not(None))
                       for m in (AlertRow, BriefSessionRow, MarketBriefRow)])
        if engine.dialect.name == "postgresql":
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            # Offline only. Preserve durable evidence in bounded memory, then
            # reclaim TOAST/table/index files without needing VACUUM FULL space.
            db.execute(text("LOCK TABLE alerts, brief_sessions, market_briefs, signal_evidence IN ACCESS EXCLUSIVE MODE"))
            protected = []
            size = 0
            for row in db.execute(select(EvidenceRow.id, EvidenceRow.body, EvidenceRow.created_at)
                                  .where(EvidenceRow.id.in_(refs))).yield_per(50):
                size += len(row.body.encode())
                if size > 64 * 1024 * 1024:
                    raise RuntimeError("Protected evidence exceeds 64 MiB; export/restore maintenance required")
                protected.append(dict(row._mapping))
            db.execute(text("TRUNCATE pulse_results, pulse_signals, market_snapshots, inference_results, signal_evidence"))
            if protected:
                db.execute(EvidenceRow.__table__.insert(), protected)
            db.commit()
            return {"reset": [m.__tablename__ for m in models], "durable_evidence_preserved": len(protected)}
        else:
            for model in models:
                db.execute(delete(model))
        # Keep the live brief and all durable editions/alerts, with their evidence.
        # Small deletion batches; do not copy a potentially GB-sized evidence table.
        db.commit()
        removed = 0
        while True:
            ids = db.scalars(select(EvidenceRow.id).where(EvidenceRow.id.not_in(refs)).limit(100)).all()
            if not ids:
                break
            removed += db.execute(delete(EvidenceRow).where(EvidenceRow.id.in_(ids))).rowcount
            db.commit()
    return {"reset": [m.__tablename__ for m in models], "orphan_evidence_deleted": removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reset-transient", action="store_true")
    args = parser.parse_args()
    print(json.dumps(storage_report(), indent=2))
    if args.reset_transient:
        print(json.dumps(reset_transient() if args.apply else {
            "preview": "Transient reset requires --apply and backend downtime; published/alert/paper records stay."
        }))
    else:
        print(json.dumps(run_retention(apply=args.apply)))


if __name__ == "__main__":
    main()
