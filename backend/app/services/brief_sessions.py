"""Durable session editions, separate from the mutable live Market Brief."""
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models.orm import BriefSessionRow
from app.models.schemas import MarketBrief
from app.services.brief_changes import compare_briefs
from app.services.brief_schedule import BriefSlot, brief_coverage_empty
from app.services.evidence import retrieve


def freeze_session(slot: BriefSlot, brief: MarketBrief | None) -> MarketBrief | None:
    """Return the original edition on retry, even after the live brief changes."""
    with SessionLocal() as db:
        row = db.get(BriefSessionRow, slot.slot_id)
        if row:
            return None if row.published_at else MarketBrief.model_validate_json(row.brief_json)
        if (not brief or brief.asset or brief.stale or not brief.evidence_id
                or not (brief.digest or brief.tldr) or brief_coverage_empty(brief)):
            return None
        evidence = retrieve(brief.evidence_id)
        if not evidence or evidence.get("kind") != "brief":
            return None
        db.add(BriefSessionRow(slot_id=slot.slot_id, label=slot.label,
                               evidence_id=brief.evidence_id, brief_json=brief.model_dump_json(),
                               frozen_at=datetime.now(timezone.utc), published_at=None))
        db.commit()
        return brief


def mark_session_published(slot_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(BriefSessionRow, slot_id)
        if row and row.published_at is None:
            row.published_at = datetime.now(timezone.utc)
            db.commit()


def latest_session_comparison() -> dict | None:
    with SessionLocal() as db:
        rows = (db.query(BriefSessionRow).filter(BriefSessionRow.published_at.is_not(None))
                .order_by(BriefSessionRow.published_at.desc(), BriefSessionRow.slot_id.desc())
                .limit(2).all())
        if not rows:
            return None
        current = rows[0]
        prior = rows[1] if len(rows) > 1 else None
        brief = MarketBrief.model_validate_json(current.brief_json)
        current_evidence = retrieve(current.evidence_id)
        prior_evidence = retrieve(prior.evidence_id) if prior else None

        def utc(value):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        comparison = (
            compare_briefs(current_evidence, prior_evidence, utc(current.published_at),
                           utc(prior.published_at) if prior else None)
            if current_evidence and (not prior or prior_evidence)
            else {"status": "unavailable", "changes": []}
        )
        return {
            **comparison, "slot_label": current.label, "baseline_label": prior.label if prior else None,
            "as_of": utc(brief.as_of), "published_at": utc(current.published_at),
            "baseline_published_at": utc(prior.published_at) if prior else None,
            "evidence_id": current.evidence_id, "stance": brief.stance,
            "read": brief.digest.read if brief.digest and brief.digest.read else
                    brief.tldr.short_read if brief.tldr else None,
        }
