"""Public article projections of durable session editions; no live data or LLM calls."""
import json
import re
from sqlalchemy import func

from app.db import SessionLocal
from app.models.orm import BriefPublicationNoteRow, BriefSessionRow
from app.models.schemas import MarketBrief
from app.services.brief_sessions import _published, _utc


def _summary(row):
    brief = MarketBrief.model_validate_json(row.brief_json)
    read = brief.digest.read.strip() if brief.digest and brief.digest.read.strip() else (
        brief.tldr.short_read.strip() if brief.tldr else "")
    return {
        "slug": row.slot_id.replace(":", "-"), "slot_id": row.slot_id,
        "label": row.label, "title": brief.headline, "description": read,
        "published_at": _utc(row.published_at).isoformat(), "as_of": _utc(brief.as_of).isoformat(),
        "stance": brief.stance.value, "source": brief.source,
    }


def list_publications(limit=20, offset=0):
    with SessionLocal() as db:
        query = _published(db)
        rows = query.offset(offset).limit(limit).all()
        modified = dict(db.query(BriefPublicationNoteRow.slot_id, func.max(BriefPublicationNoteRow.created_at))
                        .filter(BriefPublicationNoteRow.slot_id.in_([row.slot_id for row in rows]))
                        .group_by(BriefPublicationNoteRow.slot_id).all())
        return {"total": query.count(), "items": [
            {**_summary(row), "modified_at": _utc(modified.get(row.slot_id) or row.published_at).isoformat()}
            for row in rows
        ]}


def publication(slug):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-(asia|us)", slug):
        return None
    slot_id = slug[:-3] + ":us" if slug.endswith("-us") else slug[:-5] + ":asia"
    with SessionLocal() as db:
        row = db.get(BriefSessionRow, slot_id)
        if not row or not row.published_at:
            return None
        brief = MarketBrief.model_validate_json(row.brief_json)
        notes = (db.query(BriefPublicationNoteRow).filter_by(slot_id=slot_id)
                 .order_by(BriefPublicationNoteRow.created_at, BriefPublicationNoteRow.id).all())
        comparison = json.loads(row.comparison_json) if row.comparison_json else {"status": "unavailable", "changes": []}
        return {
            **_summary(row), "digest": brief.digest.model_dump() if brief.digest else None,
            "tldr": brief.tldr.model_dump() if brief.tldr else None,
            "risks": brief.risks, "suggestions": brief.suggestions,
            "comparison": comparison, "evidence_id": row.evidence_id,
            "notes": [{"id": note.id, "kind": note.kind, "text": note.body,
                       "created_at": _utc(note.created_at).isoformat()} for note in notes],
            "modified_at": _utc(notes[-1].created_at if notes else row.published_at).isoformat(),
        }
