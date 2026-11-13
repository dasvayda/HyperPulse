"""Durable session editions, separate from the mutable live Market Brief."""
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models.orm import BriefSessionRow
from app.models.schemas import MarketBrief
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
