import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.main import create_app
from app.models.orm import BriefPublicationNoteRow, BriefSessionRow
from app.services.brief_schedule import BriefSlot
from app.services.brief_sessions import freeze_session
from tests.test_brief_sessions import make_brief


@pytest.fixture
def edition():
    slot = BriefSlot("2098-12-01:asia", "asia", "Asia 09:00 KST")
    brief = make_brief()
    try:
        freeze_session(slot, brief, publish=True)
        yield slot, brief
    finally:
        with SessionLocal() as db:
            db.query(BriefPublicationNoteRow).filter_by(slot_id=slot.slot_id).delete()
            db.query(BriefSessionRow).filter_by(slot_id=slot.slot_id).delete()
            db.commit()


def test_public_article_reuses_immutable_session_without_live_or_telegram(edition, monkeypatch):
    slot, brief = edition
    monkeypatch.setattr(settings, "alerts_enabled", False)
    client = TestClient(create_app())
    path = "/api/v2/publications/2098-12-01-asia"
    original = client.get(path).json()
    freeze_session(slot, brief.model_copy(update={"headline": "Changed live brief"}), publish=True)
    assert client.get(path).json() == original
    assert original["title"] == brief.headline
    assert original["description"] == brief.tldr.short_read
    assert "context" not in original and "inputs" not in original
    index = client.get("/api/v2/publications", params={"limit": 1}).json()
    assert index["total"] >= 1 and len(index["items"]) == 1
    assert client.get("/api/v2/publications", params={"offset": index["total"]}).json()["items"] == []


def test_unpublished_and_invalid_editions_are_unavailable():
    client = TestClient(create_app())
    slot = BriefSlot("2098-12-02:us", "us", "US")
    try:
        freeze_session(slot, make_brief())
        for slug in ("2098-12-02-us", "2098-12-03-asia", "invalid", "2098-12-01-asia-extra"):
            assert client.get(f"/api/v2/publications/{slug}").status_code == 404
    finally:
        with SessionLocal() as db:
            db.query(BriefSessionRow).filter_by(slot_id=slot.slot_id).delete()
            db.commit()


def test_notes_require_token_and_append_idempotently_without_rewriting(edition, monkeypatch):
    monkeypatch.setattr(settings, "pipeline_run_token", "editor-secret")
    client = TestClient(create_app())
    path = "/api/v2/publications/2098-12-01-asia"
    before = client.get(path).json()
    payload = {"kind": "correction", "text": "Updated interpretation of the hourly funding rate."}
    assert client.post(f"{path}/notes", json=payload).status_code == 401
    headers = {"X-Pipeline-Token": "editor-secret"}
    for _ in range(2):
        response = client.post(f"{path}/notes", json=payload, headers=headers)
        assert response.status_code == 200
    result = response.json()
    assert result["title"] == before["title"] and result["digest"] == before["digest"]
    assert result["published_at"] == before["published_at"]
    assert len(result["notes"]) == 1 and result["notes"][0]["text"] == payload["text"]
    assert result["modified_at"] >= before["modified_at"]
    listed = client.get("/api/v2/publications", params={"limit": 1000}).json()["items"]
    assert next(item for item in listed if item["slug"] == "2098-12-01-asia")["modified_at"] == result["modified_at"]
    assert client.post(f"{path}/notes", json={"kind": "correction", "text": " "}, headers=headers).status_code == 422
    monkeypatch.setattr(settings, "pipeline_run_token", "")
    assert client.post(f"{path}/notes", json=payload, headers=headers).status_code == 503


def test_backend_beta_guard_stays_in_force_for_publication_api(edition, monkeypatch):
    monkeypatch.setattr(settings, "beta_access_enabled", True)
    monkeypatch.setattr(settings, "beta_api_token", "server-secret")
    client = TestClient(create_app())
    path = "/api/v2/publications/2098-12-01-asia"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Beta-Api-Token": "server-secret"}).status_code == 200


def test_empty_read_is_not_published():
    slot = BriefSlot("2098-12-03:asia", "asia", "Asia")
    brief = make_brief()
    brief.tldr.short_read = " "
    assert freeze_session(slot, brief, publish=True) is None


def test_concurrent_publishers_keep_one_original_edition(monkeypatch):
    from app.services import brief_sessions

    slot = BriefSlot("2098-12-04:asia", "asia", "Asia")
    brief = make_brief()
    barrier = Barrier(2)
    participant = local()
    retrieve = brief_sessions.retrieve

    def simultaneous_read(key):
        if key == brief.evidence_id and not getattr(participant, "waited", False):
            participant.waited = True
            barrier.wait(timeout=5)
        return retrieve(key)

    monkeypatch.setattr(brief_sessions, "retrieve", simultaneous_read)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(freeze_session, slot, brief, publish=True) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
            assert results.count(brief) == 1 and results.count(None) == 1
        with SessionLocal() as db:
            assert db.query(BriefSessionRow).filter_by(slot_id=slot.slot_id).count() == 1
    finally:
        with SessionLocal() as db:
            db.query(BriefSessionRow).filter_by(slot_id=slot.slot_id).delete()
            db.commit()
