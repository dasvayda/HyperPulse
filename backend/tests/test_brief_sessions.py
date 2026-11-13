from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import create_app
from app.models.orm import BriefSessionRow
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


def test_session_api_compares_only_published_editions():
    now = datetime.now(timezone.utc)
    slots = [BriefSlot(f"2099-01-0{i}:asia", "asia", f"Session {i}") for i in (1, 2, 3)]
    try:
        for slot, mark in zip(slots, (100, 103, 200)):
            inputs = {"top3_consensus": {"assets": ["BTC"]}, "tape": {
                "BTC": {"mark_price": mark, "funding_pct": 0, "updated_at": now.isoformat()},
            }}
            with SessionLocal() as db:
                key = save(db, envelope("brief", inputs, {}, context={}))
                db.commit()
            assert freeze_session(slot, make_brief().model_copy(update={"evidence_id": key}))
        with SessionLocal() as db:
            for index, slot in enumerate(slots[:2]):
                db.get(BriefSessionRow, slot.slot_id).published_at = now + timedelta(seconds=index)
            db.commit()
        response = TestClient(create_app()).get("/api/v2/insights/brief/session")
        assert response.status_code == 200
        result = response.json()
        assert result["slot_label"] == "Session 2"
        assert result["baseline_label"] == "Session 1"
        assert result["changes"] == [{"asset": "BTC", "metric": "mark", "delta": 3.0}]
    finally:
        with SessionLocal() as db:
            for slot in slots:
                row = db.get(BriefSessionRow, slot.slot_id)
                if row:
                    db.delete(row)
            db.commit()
