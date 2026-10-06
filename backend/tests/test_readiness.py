from datetime import timedelta

from app.config import settings
from app.services.readiness import collector_readiness, get_readiness
from app.services.store import store
from tests.conftest import NOW


def test_collector_readiness_distinguishes_starting_fresh_and_stale(monkeypatch) -> None:
    monkeypatch.setattr(settings, "collector_enabled", True)
    monkeypatch.setattr(settings, "collector_interval_seconds", 60)

    assert collector_readiness(None, now=NOW).status == "starting"
    assert collector_readiness(NOW - timedelta(seconds=30), now=NOW).status == "ok"
    assert collector_readiness(NOW - timedelta(seconds=181), now=NOW).status == "stale"


def test_collector_readiness_reports_explicit_disable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "collector_enabled", False)

    assert collector_readiness(NOW, now=NOW).status == "disabled"


def test_readiness_reports_database_cache_and_collector_separately(monkeypatch) -> None:
    monkeypatch.setattr(settings, "collector_enabled", True)
    previous = store.last_collect_at
    store.last_collect_at = NOW
    try:
        result = get_readiness(now=NOW)
    finally:
        store.last_collect_at = previous

    assert result.status == "ready"
    assert result.database.status == "ok"
    assert result.cache.status in {"ok", "fallback"}
    assert result.collector.status == "ok"
