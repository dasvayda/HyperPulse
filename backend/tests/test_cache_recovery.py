import json

import pytest
import redis

from app.services import cache


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(cache.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(cache, "_redis", None)
    monkeypatch.setattr(cache, "_retry_at", 0.0)
    monkeypatch.setattr(cache, "_memory", {})
    return now


def test_memory_fallback_obeys_expiry(clock, monkeypatch):
    monkeypatch.setattr(cache, "_get_redis", lambda: None)
    cache.cache_set("fills", {"price": 100}, ttl_seconds=10)
    clock[0] = 9
    assert cache.cache_get("fills") == {"price": 100}
    clock[0] = 10
    assert cache.cache_get("fills") is None
    assert "fills" not in cache._memory


def test_redis_recovers_after_backoff_without_replaying_fallback(clock, monkeypatch):
    class Client:
        def ping(self):
            return True

        def get(self, key):
            return json.dumps({"price": 110})

    attempts = []

    def connect(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("Offline")
        return Client()

    monkeypatch.setattr(redis, "from_url", connect)
    cache.cache_set("fills", {"price": 100}, ttl_seconds=120)
    assert cache.cache_get("fills") == {"price": 100}
    assert len(attempts) == 1
    clock[0] = 61
    assert cache.cache_get("fills") == {"price": 110}
    assert len(attempts) == 2
    assert cache._memory == {}


def test_readiness_detects_connected_redis_failure(clock, monkeypatch):
    class Client:
        def ping(self):
            raise ConnectionError("Offline")

        def close(self):
            pass

    monkeypatch.setattr(cache, "_redis", Client())
    assert cache.cache_backend_status()[0] == "fallback"
    assert cache._redis is None
    assert cache._retry_at == 60
