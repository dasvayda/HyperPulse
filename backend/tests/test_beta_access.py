import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def test_beta_blocks_direct_api_and_keeps_operator_guards(monkeypatch):
    monkeypatch.setattr(settings, "beta_access_enabled", True)
    monkeypatch.setattr(settings, "beta_api_token", "test-beta-service")
    monkeypatch.setattr(settings, "pipeline_run_token", "test-operator")
    monkeypatch.setattr(settings, "evidence_access_token", "test-evidence")
    client = TestClient(create_app())
    headers = {"X-Beta-Api-Token": "test-beta-service"}
    assert client.get("/api/v2/pipeline/status").status_code == 401
    assert client.get("/health", headers={"X-Beta-Api-Token": "wrong"}).status_code == 401
    assert client.get("/health", headers=headers).status_code == 200
    assert client.get("/api/v2/pipeline/status", headers=headers).status_code == 200
    assert client.get("/openapi.json", headers=headers).status_code == 404
    assert client.post("/api/v2/pipeline/run", headers=headers).status_code == 401
    assert client.get("/api/v2/evidence/" + "a" * 64, headers=headers).status_code == 401


def test_beta_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "beta_access_enabled", True)
    monkeypatch.setattr(settings, "beta_api_token", "")
    assert TestClient(create_app()).get("/health").status_code == 503


@pytest.mark.parametrize("path", ["/api/v2/insights/brief", "/api/v2/fear-greed"])
def test_forced_refresh_requires_operator_token(monkeypatch, path):
    from app.routers import v2
    from app.services import fear_greed

    monkeypatch.setattr(settings, "beta_access_enabled", True)
    monkeypatch.setattr(settings, "beta_api_token", "test-beta-service")
    monkeypatch.setattr(settings, "pipeline_run_token", "test-operator")
    calls = []

    async def refresh(*, force, **kwargs):
        calls.append(force)
        if path.endswith("/brief"):
            return {"headline": "Fixture", "market_status": "Fixture", "as_of": "2026-11-13T00:00:00Z"}
        return None

    monkeypatch.setattr(v2, "generate_market_brief", refresh)
    monkeypatch.setattr(fear_greed, "fetch_fear_greed", refresh)
    client = TestClient(create_app())
    headers = {"X-Beta-Api-Token": "test-beta-service"}
    assert client.get(path, headers=headers).status_code == 200
    assert client.get(path + "?force=true", headers=headers).status_code == 401
    assert calls == [False]
    assert client.get(path + "?force=true", headers={**headers, "X-Pipeline-Token": "test-operator"}).status_code == 200
    assert calls == [False, True]
