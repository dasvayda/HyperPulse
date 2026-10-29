import asyncio
from types import SimpleNamespace

import pytest

from app.collectors import scheduler
from app.services.pipeline_observability import collectors_healthy, observe_alerts, observe_stage
from app.services.store import store


@pytest.fixture(autouse=True)
def isolated_status(monkeypatch):
    monkeypatch.setattr(store, "stages", {})
    monkeypatch.setattr(store, "collectors", {})
    monkeypatch.setattr(store, "alerts", [])


def test_success_failure_and_recovery_preserve_success_time():
    async def check():
        async with observe_stage("ranking"):
            assert store.stages["ranking"].status == "running"
        success = store.stages["ranking"].last_success_at
        with pytest.raises(RuntimeError):
            async with observe_stage("ranking"):
                raise RuntimeError("secret-provider-url")
        failed = store.pipeline_status().stages["ranking"]
        assert failed.last_success_at == success
        assert failed.last_error_at and failed.duration_ms >= 0
        assert failed.consecutive_failures == 1 and failed.error_type == "RuntimeError"
        assert "secret" not in failed.model_dump_json()
        async with observe_stage("ranking"):
            pass
        assert store.stages["ranking"].consecutive_failures == 0
        assert store.stages["ranking"].last_error_at == failed.last_error_at
    asyncio.run(check())


def test_partial_collection_is_not_a_success():
    async def check():
        store.record_collection("whales", 98, 100)
        async with observe_stage("collector", healthy=collectors_healthy):
            pass
        stage = store.stages["collector"]
        assert stage.status == "degraded" and stage.last_success_at is None
    asyncio.run(check())


def test_cancellation_is_not_success_and_is_propagated():
    async def check():
        with pytest.raises(asyncio.CancelledError):
            async with observe_stage("inference"):
                raise asyncio.CancelledError()
        stage = store.stages["inference"]
        assert stage.status == "cancelled" and stage.last_success_at is None
        assert stage.consecutive_failures == 0
    asyncio.run(check())


def test_alert_cycle_with_no_candidates_is_success_but_failed_delivery_is_not():
    async def check():
        async with observe_alerts():
            pass
        success = store.stages["alerts"].last_success_at
        async with observe_alerts():
            store.alerts.append(SimpleNamespace(id="failed", status="failed"))
        assert store.stages["alerts"].status == "degraded"
        assert store.stages["alerts"].last_success_at == success
    asyncio.run(check())


def test_inference_and_alert_stages_are_independent(monkeypatch):
    async def infer():
        return []
    async def alerts(**kwargs):
        raise RuntimeError("delivery failure")
    monkeypatch.setattr(scheduler, "run_inference_pipeline", infer)
    monkeypatch.setattr(scheduler, "apply_inference_to_alerts", lambda items: items)
    monkeypatch.setattr(scheduler, "enrich_rankings_with_inference", lambda: None)
    monkeypatch.setattr(scheduler, "process_alert_triggers", alerts)
    with pytest.raises(RuntimeError):
        asyncio.run(scheduler._inference_cycle())
    assert store.stages["inference"].status == "ok"
    assert store.stages["alerts"].status == "error"


def test_same_id_failed_delivery_retry_is_not_success():
    original = SimpleNamespace(id="same", status="failed")
    store.alerts = [original]
    async def check():
        async with observe_alerts():
            store.alerts = [SimpleNamespace(id="same", status="failed")]
        assert store.stages["alerts"].status == "degraded"
    asyncio.run(check())


def test_swallowed_leaderboard_failure_is_recorded(monkeypatch):
    from app.collectors import traders
    from app.config import settings
    async def unavailable(*args):
        raise TimeoutError("private-provider-url")
    monkeypatch.setattr(settings, "use_mock_data", False)
    monkeypatch.setattr(traders, "hl_stats", unavailable)
    asyncio.run(traders.collect_top_traders())
    assert store.collectors["traders"].status == "error"
    assert not collectors_healthy()


def test_empty_leaderboard_is_not_reported_as_a_success(monkeypatch):
    from app.collectors import traders
    from app.config import settings
    async def empty(*args):
        return {"leaderboardRows": []}
    monkeypatch.setattr(settings, "use_mock_data", False)
    monkeypatch.setattr(traders, "hl_stats", empty)
    asyncio.run(traders.collect_top_traders())
    assert store.collectors["traders"].status == "error"
