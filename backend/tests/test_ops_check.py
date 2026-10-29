import argparse
from datetime import timedelta

import httpx
import pytest

from app.ops_check import ENDPOINTS, REQUIRED_STAGES, check_service, origin, positive_seconds
from tests.conftest import NOW


def payloads():
    return {
        "/health": {"status": "ok"},
        "/health/ready": {"status": "ready", "database": {"status": "ok"},
                          "collector": {"status": "ok"}, "cache": {"status": "ok"}},
        "/api/v2/pipeline/status": {"telegram_configured": True, "stages": {
            name: {"status": "ok", "last_success_at": NOW.isoformat()} for name in REQUIRED_STAGES}},
        "/api/v2/alerts/summary": {"sent": 0, "failed": 0, "queued": 0, "attempted": 0},
    }


def run_check(body, responses=None):
    calls = []
    def transport(request):
        calls.append((request.method, request.url.path))
        if responses and request.url.path in responses:
            value = responses[request.url.path]
            if isinstance(value, Exception):
                raise value
            return value
        return httpx.Response(200, json=body[request.url.path])
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        result = check_service(client, "http://localhost:8100", now=NOW)
    return result, calls


def test_healthy_check_only_makes_four_read_only_calls():
    result, calls = run_check(payloads())
    assert result["exit_code"] == 0
    assert calls == [("GET", path) for path in ENDPOINTS.values()]


def test_cache_fallback_and_delivery_failures_are_warnings():
    body = payloads()
    body["/health/ready"]["cache"]["status"] = "fallback"
    body["/api/v2/alerts/summary"]["failed"] = 1
    body["/api/v2/alerts/summary"]["attempted"] = 1
    result, _ = run_check(body)
    assert result["status"] == "warning" and result["exit_code"] == 1


@pytest.mark.parametrize("response", [httpx.Response(503, json={"status": "degraded"}),
    httpx.Response(302, headers={"Location": "https://unexpected.example"}),
    httpx.Response(200, text="not json"), httpx.Response(200, json=[]), httpx.Response(200, json={}),
    httpx.ReadTimeout("secret-provider-url")])
def test_unavailable_or_malformed_health_never_reports_healthy(response):
    result, calls = run_check(payloads(), {"/health/ready": response})
    assert result["exit_code"] == 2
    assert "secret-provider-url" not in str(result)
    assert len(calls) == 4


@pytest.mark.parametrize("status", ["error", "degraded", "unknown"])
def test_stage_failures_are_critical(status):
    body = payloads()
    body["/api/v2/pipeline/status"]["stages"]["alerts"]["status"] = status
    assert run_check(body)[0]["exit_code"] == 2


def test_stuck_running_and_old_success_are_critical():
    for status, field in (("running", "started_at"), ("ok", "last_success_at")):
        body = payloads()
        body["/api/v2/pipeline/status"]["stages"]["inference"] = {
            "status": status, field: (NOW - timedelta(minutes=11)).isoformat()}
        assert run_check(body)[0]["exit_code"] == 2


def test_slow_leaderboard_cadence_is_not_a_false_alarm():
    body = payloads()
    body["/api/v2/pipeline/status"]["stages"]["trader_refresh"]["last_success_at"] = (NOW - timedelta(minutes=16)).isoformat()
    assert run_check(body)[0]["exit_code"] == 0


def test_missing_status_and_invalid_delivery_counts_are_critical():
    body = payloads()
    body["/api/v2/pipeline/status"]["stages"] = {}
    assert run_check(body)[0]["exit_code"] == 2
    body = payloads()
    body["/api/v2/alerts/summary"]["failed"] = "not-a-count"
    assert run_check(body)[0]["exit_code"] == 2


@pytest.mark.parametrize("value", ["https://user:password@example.com", "file:///tmp/x",
    "https://example.com?token=secret", "http://localhost/path"])
def test_origin_rejects_credentials_and_non_origin_urls(value):
    with pytest.raises(argparse.ArgumentTypeError):
        origin(value)


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_timeout_must_be_bounded_positive_number(value):
    with pytest.raises(argparse.ArgumentTypeError):
        positive_seconds(value)
