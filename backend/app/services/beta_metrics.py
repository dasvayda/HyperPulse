"""Opt-in Beta visits, deduplicated by browser, event, subject and UTC day."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models.orm import BetaVisitRow, BriefSessionRow


class BetaVisit(BaseModel):
    visitor: UUID
    event: Literal["session_view", "telegram_evidence", "scorecard_view"]
    subject: str = Field(max_length=64, pattern=r"^[a-z0-9:-]*$")


def record_visit(visit: BetaVisit, *, now=None) -> None:
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    visitor = str(visit.visitor)
    key = sha256(f"{visitor}|{visit.event}|{visit.subject}|{day}".encode()).hexdigest()
    with SessionLocal() as db:
        if visit.event == "session_view":
            session = db.get(BriefSessionRow, visit.subject)
            if not session or not session.published_at:
                return
        db.add(BetaVisitRow(id=key, visitor=visitor, event=visit.event, subject=visit.subject,
                            day=day, visited_at=now))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if db.get(BetaVisitRow, key) is None:
                raise


def visit_summary(days: int, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    since = (now.date() - timedelta(days=days - 1)).isoformat()
    with SessionLocal() as db:
        visits = db.query(BetaVisitRow).filter(BetaVisitRow.day >= since).all()
        slots = [row[0] for row in db.query(BriefSessionRow.slot_id)
                 .filter(BriefSessionRow.published_at.is_not(None),
                         BriefSessionRow.published_at >= now - timedelta(days=days))
                 .order_by(BriefSessionRow.published_at, BriefSessionRow.slot_id)]
    viewers, scorecard, telegram = defaultdict(dict), defaultdict(set), set()
    for row in visits:
        if row.event == "session_view":
            times = viewers[row.subject]
            times[row.visitor] = min(times.get(row.visitor, row.visited_at), row.visited_at)
        elif row.event == "scorecard_view":
            scorecard[row.visitor].add(row.day)
        else:
            telegram.add(row.visitor)
    pairs = list(zip(slots, slots[1:]))
    return {
        "since_utc": since, "session_pairs": len(pairs),
        "eligible_session_browser_pairs": sum(len(viewers[a]) for a, _ in pairs),
        "next_session_browser_pairs": sum(
            visitor in viewers[b] and when < viewers[b][visitor]
            for a, b in pairs for visitor, when in viewers[a].items()
        ),
        "telegram_evidence_browsers": len(telegram),
        "scorecard_browsers": len(scorecard),
        "scorecard_return_browsers": sum(len(dates) > 1 for dates in scorecard.values()),
    }
