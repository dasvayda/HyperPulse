from datetime import datetime, timezone

from app.db import SessionLocal
from app.models.schemas import MarketBrief
from app.services.brief_schedule import BriefSlot
from app.services.brief_sessions import freeze_session, mark_session_published
from app.services.evidence import envelope, save


def make_brief():
    with SessionLocal() as db:
        key = save(db, envelope("brief", {}, {}, context={}))
        db.commit()
    return MarketBrief(
        headline="Original", market_status="Test market",
        as_of=datetime.now(timezone.utc), evidence_id=key,
        tldr={"now": "BTC", "short_read": "Test read", "however": "Test caution"},
    )


def test_session_retry_reuses_original_and_publication_stops_retry():
    slot = BriefSlot("2026-11-14:asia", "asia", "Asia")
    brief = make_brief()
    assert freeze_session(slot, brief) == brief
    assert freeze_session(slot, brief.model_copy(update={"headline": "New live brief"})) == brief
    assert freeze_session(slot, None) == brief
    mark_session_published(slot.slot_id)
    mark_session_published(slot.slot_id)
    assert freeze_session(slot, brief) is None


def test_no_session_for_stale_coin_or_missing_evidence():
    slot = BriefSlot("2026-11-14:us", "us", "US")
    brief = make_brief()
    for update in ({"stale": True}, {"asset": "BTC"}, {"evidence_id": "unknown"}):
        assert freeze_session(slot, brief.model_copy(update=update)) is None
