from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import create_app
from app.models.orm import BetaVisitRow, BriefSessionRow
from app.services.beta_metrics import BetaVisit, record_visit, visit_summary


def test_beta_metrics_default_off_and_operator_read_protected(monkeypatch):
    monkeypatch.setattr(settings, "beta_access_enabled", True)
    monkeypatch.setattr(settings, "beta_api_token", "beta-test")
    monkeypatch.setattr(settings, "pipeline_run_token", "operator-test")
    monkeypatch.setattr(settings, "beta_metrics_enabled", False)
    client = TestClient(create_app())
    headers = {"X-Beta-Api-Token": "beta-test"}
    body = {"visitor": str(uuid4()), "event": "scorecard_view", "subject": ""}
    assert client.post("/api/v2/beta/visits", headers=headers, json=body).status_code == 404
    monkeypatch.setattr(settings, "beta_metrics_enabled", True)
    assert client.post("/api/v2/beta/visits", json=body).status_code == 401
    assert client.get("/api/v2/beta/visits/summary", headers=headers).status_code == 401
    assert client.get("/api/v2/beta/visits/summary", headers={
        **headers, "X-Pipeline-Token": "operator-test"}).status_code == 200


def test_visit_counts_dedupe_and_require_forward_session_order():
    now = datetime(2096, 1, 2, tzinfo=timezone.utc)
    slots = ("2096-01-01:us", "2096-01-02:asia")
    visitors = [uuid4(), uuid4()]
    with SessionLocal() as db:
        for i, slot in enumerate(slots):
            db.add(BriefSessionRow(slot_id=slot, label="test", evidence_id="fixture",
                                   brief_json="{}", frozen_at=now, published_at=now + timedelta(minutes=i)))
        db.commit()
    try:
        for index, visitor in enumerate(visitors):
            for i, slot in enumerate(slots if index == 0 else slots[::-1]):
                visit = BetaVisit(visitor=visitor, event="session_view", subject=slot)
                record_visit(visit, now=now + timedelta(minutes=2 + i))
                record_visit(visit, now=now + timedelta(minutes=3 + i))
        report = visit_summary(2, now=now + timedelta(hours=1))
        assert report["eligible_session_browser_pairs"] == 2
        assert report["next_session_browser_pairs"] == 1
    finally:
        with SessionLocal() as db:
            db.query(BetaVisitRow).filter(BetaVisitRow.visitor.in_([str(v) for v in visitors])).delete(synchronize_session=False)
            db.query(BriefSessionRow).filter(BriefSessionRow.slot_id.in_(slots)).delete(synchronize_session=False)
            db.commit()
