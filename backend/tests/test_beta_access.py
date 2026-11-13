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
