from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_memory: dict[str, str] = {}
_redis = None
_redis_failed = False


def _get_redis():
    global _redis, _redis_failed
    if _redis_failed:
        return None
    if _redis is not None:
        return _redis
    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _redis = client
        logger.info("Redis cache connected")
        return _redis
    except Exception as exc:
        _redis_failed = True
        logger.warning("Redis unavailable, using memory cache: %s", exc)
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    payload = json.dumps(value, default=str)
    client = _get_redis()
    if client is not None:
        try:
            client.setex(key, ttl_seconds, payload)
            return
        except Exception as exc:
            logger.warning("Redis set failed: %s", exc)
    _memory[key] = payload


def cache_get(key: str) -> Any | None:
    client = _get_redis()
    if client is not None:
        try:
            payload = client.get(key)
            if payload is not None:
                return json.loads(payload)
        except Exception as exc:
            logger.warning("Redis get failed: %s", exc)
    payload = _memory.get(key)
    if payload is None:
        return None
    return json.loads(payload)
