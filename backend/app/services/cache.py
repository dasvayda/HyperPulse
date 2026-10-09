from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_memory: dict[str, tuple[str, float]] = {}
_redis = None
_retry_at = 0.0
RECONNECT_SECONDS = 60


def _disconnect() -> None:
    global _redis, _retry_at
    client, _redis = _redis, None
    _retry_at = time.monotonic() + RECONNECT_SECONDS
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    if time.monotonic() < _retry_at:
        return None
    try:
        import redis

        client = redis.from_url(
            settings.redis_url, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        client.ping()
        _redis = client
        # Redis is authoritative after reconnect. Do not replay fallback values
        # that may be older than a value written by another process.
        _memory.clear()
        logger.info("Redis cache connected")
        return _redis
    except Exception as exc:
        _disconnect()
        logger.warning("Redis unavailable, using memory cache (%s)", type(exc).__name__)
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    payload = json.dumps(value, default=str)
    client = _get_redis()
    if client is not None:
        try:
            if ttl_seconds > 0:
                client.setex(key, ttl_seconds, payload)
            else:
                client.delete(key)
            _memory.pop(key, None)
            return
        except Exception as exc:
            _disconnect()
            logger.warning("Redis set failed (%s)", type(exc).__name__)
    if ttl_seconds > 0:
        now = time.monotonic()
        for expired in [k for k, (_, until) in _memory.items() if until <= now]:
            _memory.pop(expired, None)
        _memory[key] = (payload, now + ttl_seconds)
    else:
        _memory.pop(key, None)


def cache_get(key: str) -> Any | None:
    client = _get_redis()
    if client is not None:
        try:
            payload = client.get(key)
            if payload is not None:
                return json.loads(payload)
        except Exception as exc:
            _disconnect()
            logger.warning("Redis get failed (%s)", type(exc).__name__)
    cached = _memory.get(key)
    if cached is None:
        return None
    payload, expires_at = cached
    if time.monotonic() >= expires_at:
        _memory.pop(key, None)
        return None
    return json.loads(payload)


def cache_backend_status() -> tuple[str, str]:
    """Return the active cache mode without treating Redis fallback as an outage."""

    client = _get_redis()
    if client is not None:
        try:
            client.ping()
            return "ok", "Redis cache connected"
        except Exception:
            _disconnect()
    return "fallback", "Redis unavailable; using in-memory cache"
