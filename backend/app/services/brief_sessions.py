"""Durable session editions, separate from the mutable live Market Brief."""
import json
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.orm import BriefSessionRow
from app.models.schemas import MarketBrief
from app.services.brief_changes import compare_briefs
from app.services.brief_schedule import BriefSlot, brief_coverage_empty, current_brief_slot
from app.services.evidence import retrieve


def _utc(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _compare(evidence, prior, at):
    previous = retrieve(prior.evidence_id) if prior else None
    result = (compare_briefs(evidence, previous, _utc(at), _utc(prior.published_at) if prior else None)
              if evidence and (not prior or previous) else {"status": "unavailable", "changes": []})
    return {**result, "baseline_label": prior.label if prior else None,
            "baseline_published_at": _utc(prior.published_at).isoformat() if prior else None}


def _published(db):
    return (db.query(BriefSessionRow).filter(BriefSessionRow.published_at.is_not(None))
            .order_by(BriefSessionRow.published_at.desc(), BriefSessionRow.slot_id.desc()))


def freeze_session(slot: BriefSlot, brief: MarketBrief | None, *, publish: bool = False) -> MarketBrief | None:
    """Return the original edition on retry, even after the live brief changes."""
    with SessionLocal() as db:
        row = db.get(BriefSessionRow, slot.slot_id)
        if row:
            if publish and row.published_at is None:
                db.query(BriefSessionRow).filter(
                    BriefSessionRow.slot_id == slot.slot_id, BriefSessionRow.published_at.is_(None),
                ).update({BriefSessionRow.published_at: datetime.now(timezone.utc)})
                db.commit()
                return MarketBrief.model_validate_json(row.brief_json)
            return None if row.published_at else MarketBrief.model_validate_json(row.brief_json)
        if (not brief or brief.asset or brief.stale or not brief.evidence_id
                or not (brief.digest or brief.tldr) or brief_coverage_empty(brief)):
            return None
        read = (brief.digest.read.strip() if brief.digest else "") or (brief.tldr.short_read.strip() if brief.tldr else "")
        if not read.strip():
            return None
        evidence = retrieve(brief.evidence_id)
        if not evidence or evidence.get("kind") != "brief":
            return None
        now = datetime.now(timezone.utc)
        comparison = _compare(evidence, _published(db).first(), now)
        db.add(BriefSessionRow(slot_id=slot.slot_id, label=slot.label,
                               evidence_id=brief.evidence_id, brief_json=brief.model_dump_json(),
                               comparison_json=json.dumps(comparison), frozen_at=now, published_at=now if publish else None))
        try:
            db.commit()
        except IntegrityError:
            # A concurrent publisher can win the unique session key. Reuse its edition.
            db.rollback()
            if db.get(BriefSessionRow, slot.slot_id) is None:
                raise
            return freeze_session(slot, brief, publish=publish)
        return brief


def publish_due_session(brief: MarketBrief | None) -> None:
    slot = current_brief_slot()
    if slot:
        freeze_session(slot, brief, publish=True)


def published_session_brief(slot_id: str) -> MarketBrief | None:
    with SessionLocal() as db:
        row = db.get(BriefSessionRow, slot_id)
        return MarketBrief.model_validate_json(row.brief_json) if row and row.published_at else None


def recent_sessions(limit: int) -> list[dict]:
    with SessionLocal() as db:
        return [{"slot_id": row.slot_id, "slot_label": row.label, "published_at": _utc(row.published_at)}
                for row in _published(db).limit(limit)]


def mark_session_published(slot_id: str) -> None:
    with SessionLocal() as db:
        db.query(BriefSessionRow).filter(
            BriefSessionRow.slot_id == slot_id, BriefSessionRow.published_at.is_(None),
        ).update({BriefSessionRow.published_at: datetime.now(timezone.utc)})
        db.commit()


def session_change_line(slot_id: str) -> str:
    with SessionLocal() as db:
        row = db.get(BriefSessionRow, slot_id)
        result = json.loads(row.comparison_json) if row and row.comparison_json else {}
    changes = result.get("changes", [])
    if changes:
        item = changes[0]
        label, unit = {"mark": ("mark", "%"), "funding": ("hourly funding", " pp"),
                       "whale_long_share": ("tracked whale long share", " pp")}[item["metric"]]
        return f"Since last session: {item['asset']} {label} {item['delta']:+.4g}{unit}"
    return {
        "no_baseline": "First session · no prior brief to compare.",
        "unchanged": "No large change since the previous session.",
        "partial": "No large change in comparable inputs · some data could not be compared.",
    }.get(result.get("status"), "Session comparison unavailable.")


def latest_session_comparison(slot_id: str | None = None) -> dict | None:
    with SessionLocal() as db:
        query = _published(db)
        current = (query.filter(BriefSessionRow.slot_id == slot_id) if slot_id else query).first()
        if not current:
            return None
        brief = MarketBrief.model_validate_json(current.brief_json)
        prior = query.filter(BriefSessionRow.published_at < current.published_at).first()
        comparison = (json.loads(current.comparison_json) if current.comparison_json
                      else _compare(retrieve(current.evidence_id), prior, current.published_at))
        return {
            **comparison, "slot_id": current.slot_id, "slot_label": current.label,
            "as_of": _utc(brief.as_of), "published_at": _utc(current.published_at),
            "evidence_id": current.evidence_id, "stance": brief.stance,
            "read": brief.digest.read if brief.digest and brief.digest.read else
                    brief.tldr.short_read if brief.tldr else None,
        }
