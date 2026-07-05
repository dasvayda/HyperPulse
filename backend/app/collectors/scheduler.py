from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.collectors.hyperliquid import collect_market_snapshot
from app.collectors.traders import collect_top_traders
from app.collectors.liquidations import collect_liquidation_events
from app.collectors.whales import collect_whale_events
from app.services.alerts import process_alert_triggers
from app.services.inference import apply_inference_to_alerts, run_inference_pipeline
from app.services.ranking import run_ranking_pipeline
from app.services.store import store

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []
_started = False


async def _loop(name: str, interval: int, coro_factory) -> None:
    while True:
        try:
            await coro_factory()
        except Exception:
            logger.exception("Background task failed: %s", name)
        await asyncio.sleep(interval)


async def _collect_cycle() -> None:
    await collect_top_traders()
    snapshot = await collect_market_snapshot()
    await collect_liquidation_events()
    await collect_whale_events()
    logger.info("Collector cycle complete: %s", snapshot)


async def _inference_cycle() -> None:
    results = await run_inference_pipeline()
    store.whale_alerts = apply_inference_to_alerts(store.whale_alerts)
    await process_alert_triggers(
        whale_alerts=store.whale_alerts[:3],
        zones=[z for z in store.liquidation_zones if z.size_usd >= 100_000_000][:2],
        inferences=results,
    )
    logger.info("Inference cycle complete: %s results", len(results))


async def _ranking_cycle() -> None:
    rankings = run_ranking_pipeline()
    logger.info("Ranking cycle complete: top=%s", rankings[0].alias if rankings else None)


async def run_bootstrap_pipeline() -> None:
    """Run one collect pass so the API can serve live data quickly on startup."""
    await _collect_cycle()
    await _ranking_cycle()
    logger.info("Bootstrap pipeline complete (inference/alerts deferred to background)")


def start_background_tasks() -> None:
    global _started
    if _started:
        return
    _started = True

    if settings.collector_enabled:
        _tasks.append(
            asyncio.create_task(
                _loop("collector", settings.collector_interval_seconds, _collect_cycle)
            )
        )
    _tasks.append(
        asyncio.create_task(
            _loop("inference", settings.inference_interval_seconds, _inference_cycle)
        )
    )
    _tasks.append(
        asyncio.create_task(
            _loop("ranking", settings.ranking_interval_seconds, _ranking_cycle)
        )
    )
    logger.info("Background pipeline tasks started")


async def stop_background_tasks() -> None:
    global _started
    for task in _tasks:
        task.cancel()
    for task in _tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    _tasks.clear()
    _started = False
