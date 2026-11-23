from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def test_infrastructure_probe_is_public_while_api_remains_protected(monkeypatch):
    monkeypatch.setattr(settings, "beta_access_enabled", True)
    monkeypatch.setattr(settings, "beta_api_token", "test-service-token")
    client = TestClient(create_app())
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health").status_code == 401
    assert client.get("/api/v2/pipeline/status").status_code == 401
