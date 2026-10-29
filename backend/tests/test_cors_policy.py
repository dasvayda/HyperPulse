import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import create_app


@pytest.mark.parametrize("origin", ["*", "null", "http://app.example.com", "https://*.example.com",
    "https://user:password@example.com", "https://app.example.com/path",
    "https://app.example.com?token=secret", "https://app.example.com#fragment", "", "https://example.com:bad"])
def test_production_rejects_unsafe_origins(origin):
    config = Settings(_env_file=None, environment="production", cors_origins=origin)
    with pytest.raises(ValueError) as exc:
        _ = config.cors_origin_list
    assert "password" not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_local_origins_and_normalization():
    config = Settings(_env_file=None, environment="development",
                      cors_origins="http://localhost:3100/, ,http://localhost:3100")
    assert config.cors_origin_list == ["http://localhost:3100"]
    config.cors_origins = "*"
    assert config.cors_origin_list == ["*"]
    config.cors_allow_credentials = True
    with pytest.raises(ValueError):
        _ = config.cors_origin_list


def test_real_preflight_only_allows_configured_production_origin(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example.com")
    monkeypatch.setattr(settings, "cors_allow_credentials", False)
    # No lifespan: no live collectors, AI requests, or Telegram sends.
    client = TestClient(create_app())
    headers = {"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "X-Pipeline-Token"}
    allowed = client.options("/api/v2/pipeline/run", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-credentials" not in allowed.headers
    headers["Origin"] = "https://evil.example.com"
    denied = client.options("/api/v2/pipeline/run", headers=headers)
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_application_fails_before_serving_with_unsafe_production_cors(monkeypatch):
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "cors_origins", "*")
    with pytest.raises(ValueError):
        create_app()
