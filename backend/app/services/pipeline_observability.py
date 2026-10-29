"""Process-local cycle health, not an assertion that a signal or trade is correct."""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Callable

from app.services.store import store


def collectors_healthy() -> bool:
    return bool(store.collectors) and all(item.status == "ok" for item in store.collectors.values())


@asynccontextmanager
async def observe_stage(name: str, *, healthy: Callable[[], bool] | None = None):
    started = time.monotonic()
    store.record_stage_start(name)
    try:
        yield
        status = "ok" if healthy is None or healthy() else "degraded"
    except asyncio.CancelledError:
        store.record_stage_finish(name, "cancelled", (time.monotonic() - started) * 1000)
        raise
    except Exception as exc:
        # Never put exception messages, payloads or provider URLs in the public status.
        store.record_stage_finish(name, "error", (time.monotonic() - started) * 1000, type(exc).__name__)
        raise
    else:
        store.record_stage_finish(name, status, (time.monotonic() - started) * 1000)


@asynccontextmanager
async def observe_alerts():
    previous = {item.id: item for item in store.alerts}
    async with observe_stage("alerts", healthy=lambda: all(
        item.status == "sent" for item in store.alerts if previous.get(item.id) is not item
    )):
        yield
