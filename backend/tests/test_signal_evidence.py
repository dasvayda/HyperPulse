import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal
from app.models.orm import EvidenceRow
from app.services import evidence, market_brief
from app.services.store import store
from tests.conftest import seed_store


def test_brief_evidence_survives_live_input_change_and_reload(monkeypatch):
    seed_store()
    monkeypatch.setattr(settings, "ai_provider", "heuristic")
    brief = asyncio.run(market_brief.generate_market_brief(force=True))
    saved = evidence.retrieve(brief.evidence_id)
    assert saved["inputs"]["tape"]["BTC"]["mark_price"] == 76844
    store.market_ticks["BTC"]["mark_price"] = 1
    store.rankings = []
    assert evidence.retrieve(brief.evidence_id) == saved
    loaded = market_brief.load_market_brief_from_db()
    assert loaded.evidence_id == brief.evidence_id


def test_brief_save_failure_returns_previous_stale_and_no_new_evidence(monkeypatch):
    seed_store()
    monkeypatch.setattr(settings, "ai_provider", "heuristic")
    previous = asyncio.run(market_brief.generate_market_brief(force=True))
    def fail(*args, **kwargs): raise RuntimeError("storage failure")
    monkeypatch.setattr(market_brief, "persist_market_brief", fail)
    result = asyncio.run(market_brief.generate_market_brief(force=True))
    assert result.stale and result.evidence_id == previous.evidence_id


def test_evidence_endpoint_access_missing_and_tampering(monkeypatch):
    from app.main import app
    with SessionLocal() as db:
        key = evidence.save(db, evidence.envelope("test", {"price": 100}, {}, context={}))
        db.commit()
    monkeypatch.setattr(settings, "evidence_access_token", "test-invite")
    client = TestClient(app)
    assert client.get(f"/api/v2/evidence/{key}").status_code == 401
    response = client.get(f"/api/v2/evidence/{key}", headers={"X-Evidence-Token": "test-invite"})
    assert response.status_code == 200 and response.json()["inputs"]["price"] == 100
    assert client.get("/api/v2/evidence/" + "0" * 64, headers={"X-Evidence-Token": "test-invite"}).status_code == 404
    with SessionLocal() as db:
        db.get(EvidenceRow, key).body = "{}"
        db.commit()
    with pytest.raises(ValueError): evidence.retrieve(key)


def test_rule_cards_reference_frozen_saved_inputs(monkeypatch):
    from app.services.inference import _build_market_insights
    seed_store()
    _build_market_insights()
    assert store.insights
    saved = evidence.retrieve(store.insights[0].evidence_id)
    assert saved["kind"] == "rule_insights"
    assert saved["outputs"][0]["id"] == store.insights[0].id
    store.market_ticks.clear()
    assert saved == evidence.retrieve(store.insights[0].evidence_id)


def test_alert_evidence_save_failure_prevents_external_delivery(monkeypatch):
    from app.services import alerts
    monkeypatch.setattr(settings, "alerts_enabled", True)
    monkeypatch.setattr(alerts, "_is_rate_limited", lambda *args: False)
    monkeypatch.setattr(alerts, "_is_type_rate_limited", lambda *args: False)
    monkeypatch.setattr(alerts, "_is_recent_duplicate", lambda *args: False)
    sent = []
    async def send(*args): sent.append(True); return True
    monkeypatch.setattr(alerts, "_send_telegram", send)
    def fail(*args): raise RuntimeError("db failure")
    monkeypatch.setattr(evidence, "save", fail)
    with pytest.raises(RuntimeError): asyncio.run(alerts._dispatch("test", "test", ["test"], {}))
    assert not sent


def test_live_brief_missing_liquidations_are_not_quiet(monkeypatch):
    seed_store()
    monkeypatch.setattr(settings, "use_mock_data", False)
    snapshot = market_brief.build_market_brief_snapshot()
    assert snapshot["liq_1h"]["total_usd"] is None
    assert snapshot["liq_1h"]["status"] == "unavailable"
    brief = market_brief.build_template_brief(snapshot)
    assert "unavailable" in json.dumps(brief.model_dump(mode="json"))


def test_rule_save_failure_preserves_previous_as_stale(monkeypatch):
    from app.services.inference import _build_market_insights
    seed_store()
    _build_market_insights()
    ids = [i.id for i in store.insights]
    def fail(*args): raise RuntimeError("storage failed")
    monkeypatch.setattr(evidence, "save", fail)
    with pytest.raises(RuntimeError): _build_market_insights()
    assert [i.id for i in store.insights] == ids
    assert all(i.stale for i in store.insights)


def test_production_evidence_fails_closed_without_token(monkeypatch):
    from app.main import app
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "evidence_access_token", "")
    assert TestClient(app).get("/api/v2/evidence/" + "0" * 64).status_code == 503


def test_alert_persists_evidence_and_reloads_with_same_id(monkeypatch):
    from app.services import alerts
    from app.models.orm import AlertRow
    seed_store()
    monkeypatch.setattr(settings, "alerts_enabled", True)
    monkeypatch.setattr(alerts, "_is_rate_limited", lambda *args: False)
    monkeypatch.setattr(alerts, "_is_type_rate_limited", lambda *args: False)
    monkeypatch.setattr(alerts, "_is_recent_duplicate", lambda *args: False)
    async def send(*args): return True
    monkeypatch.setattr(alerts, "_send_telegram", send)
    item = asyncio.run(alerts._dispatch("test", "test", ["test"], {"delta_usd": 123}))
    assert item.evidence_id
    assert evidence.retrieve(item.evidence_id)["inputs"]["trigger"]["delta_usd"] == 123
    with SessionLocal() as db:
        assert db.get(AlertRow, item.id).evidence_id == item.evidence_id
