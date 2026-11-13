"""Durable session editions, separate from the mutable live Market Brief."""
import json
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models.orm import BriefSessionRow
from app.models.schemas import MarketBrief
from app.services.brief_changes import compare_briefs
from app.services.brief_schedule import BriefSlot, brief_coverage_empty
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
        now = datetime.now(timezone.utc)
        comparison = _compare(evidence, _published(db).first(), now)
        db.add(BriefSessionRow(slot_id=slot.slot_id, label=slot.label,
                               evidence_id=brief.evidence_id, brief_json=brief.model_dump_json(),
                               comparison_json=json.dumps(comparison), frozen_at=now, published_at=None))
        db.commit()
        return brief


def mark_session_published(slot_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(BriefSessionRow, slot_id)
        if row and row.published_at is None:
            row.published_at = datetime.now(timezone.utc)
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
            **comparison, "slot_label": current.label,
            "as_of": _utc(brief.as_of), "published_at": _utc(current.published_at),
            "evidence_id": current.evidence_id, "stance": brief.stance,
            "read": brief.digest.read if brief.digest and brief.digest.read else
                    brief.tldr.short_read if brief.tldr else None,
        }
