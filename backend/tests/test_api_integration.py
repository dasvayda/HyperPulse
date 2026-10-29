"""HTTP contract checks on the real app/router/middleware, no live lifespan."""
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.models.schemas import ReadinessComponent, ReadinessStatus
from app.services.store import store
from app.routers import v2


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "cors_origins", "https://app.example.com")
    monkeypatch.setattr(settings, "api_docs_enabled", False)
    monkeypatch.setattr(settings, "pipeline_run_token", "integration-fake-token")
    monkeypatch.setattr(store, "alerts", [])
    monkeypatch.setattr(store, "collectors", {})
    monkeypatch.setattr(store, "stages", {})
    # No context manager => no lifespan => no bootstrap or scheduled side effects.
    return TestClient(main.create_app(), raise_server_exceptions=False)


def test_liveness_and_disabled_docs_contract(client):
    result = client.get("/health")
    assert result.status_code == 200 and result.json()["status"] == "ok"
    assert "telegram_bot_token" not in result.text
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("ready", [True, False])
def test_readiness_http_status_matches_components(client, monkeypatch, ready):
    now = datetime.now(timezone.utc)
    ok = ReadinessComponent(status="ok", detail="Test component", checked_at=now)
    db = ok if ready else ok.model_copy(update={"status": "error"})
    monkeypatch.setattr(main, "get_readiness", lambda: ReadinessStatus(
        status="ready" if ready else "degraded", database=db, cache=ok, collector=ok))
    response = client.get("/health/ready")
    assert response.status_code == (200 if ready else 503)
    assert response.json()["database"]["status"] == ("ok" if ready else "error")


def test_status_serializes_stage_health_without_exception_message(client):
    store.record_stage_start("ranking")
    store.record_stage_finish("ranking", "error", 12.34, "TimeoutError")
    response = client.get("/api/v2/pipeline/status")
    assert response.status_code == 200
    stage = response.json()["stages"]["ranking"]
    assert stage["status"] == "error" and stage["error_type"] == "TimeoutError"
    assert stage["duration_ms"] == 12.34 and stage["consecutive_failures"] == 1
    assert "integration-fake-token" not in response.text


@pytest.mark.parametrize("token", [None, "wrong-token"])
def test_unauthorized_pipeline_request_never_executes_work(client, monkeypatch, token):
    from app.collectors import hyperliquid
    async def forbidden():
        pytest.fail("Unauthorized pipeline executed")
    monkeypatch.setattr(hyperliquid, "collect_market_snapshot", forbidden)
    response = client.post("/api/v2/pipeline/run", headers={"X-Pipeline-Token": token} if token else {})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid pipeline run token"}


def test_missing_operations_token_fails_closed_over_http(client, monkeypatch):
    monkeypatch.setattr(settings, "pipeline_run_token", "")
    assert client.post("/api/v2/pipeline/run").status_code == 503


def test_authorized_pipeline_with_stubbed_dependencies_records_stages(client, monkeypatch):
    from app.collectors import hyperliquid
    calls = []
    async def collect():
        calls.append("collect")
        store.record_collection("market", 1, 1)
    async def infer():
        calls.append("infer")
        return []
    async def alerts(**kwargs):
        calls.append("alerts")
    monkeypatch.setattr(hyperliquid, "collect_market_snapshot", collect)
    monkeypatch.setattr(v2, "run_inference_pipeline", infer)
    monkeypatch.setattr(v2, "run_ranking_pipeline", lambda: calls.append("rank"))
    monkeypatch.setattr(v2, "run_paper_portfolio", lambda: calls.append("paper"))
    monkeypatch.setattr(v2, "process_alert_triggers", alerts)
    response = client.post("/api/v2/pipeline/run", headers={"X-Pipeline-Token": "integration-fake-token"})
    assert response.status_code == 200
    assert calls == ["collect", "infer", "rank", "paper", "alerts"]
    assert all(stage["status"] == "ok" for stage in response.json()["stages"].values())


def test_unhandled_dependency_failure_is_generic_not_a_secret_dump(client, monkeypatch):
    def failed():
        raise RuntimeError("secret-test-token-internal-dsn")
    monkeypatch.setattr(main, "get_readiness", failed)
    response = client.get("/health/ready")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "secret-test" not in response.text


def test_empty_alert_history_and_summary_have_valid_contracts(client):
    assert client.get("/api/v2/alerts").json() == []
    response = client.get("/api/v2/alerts/summary")
    assert response.status_code == 200
    assert response.json()["attempted"] == 0
    assert response.json()["delivery_rate_pct"] is None


def test_external_http_is_blocked_unless_explicitly_mocked():
    with pytest.raises(AssertionError, match="External HTTP disabled"):
        httpx.get("https://example.invalid/no-real-network")
