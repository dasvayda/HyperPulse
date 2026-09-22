from __future__ import annotations

import asyncio
import logging
import time

from app.config import settings
from app.collectors.hyperliquid import collect_market_snapshot
from app.collectors.traders import collect_top_traders
from app.collectors.liquidations import collect_liquidation_events
from app.collectors.whales import collect_whale_events
from app.services.alerts import process_alert_triggers
from app.services.inference import (
    apply_inference_to_alerts,
    enrich_rankings_with_inference,
    run_inference_pipeline,
)
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
    snapshot = await collect_market_snapshot()
    await collect_liquidation_events()
    await collect_whale_events()
    try:
        from app.services.pulse import resolve_due_pulses

        n = resolve_due_pulses()
        if n:
            logger.info("Pulse resolve: %s signals", n)
    except Exception:
        logger.exception("Pulse resolve in collect cycle failed")
    logger.info("Collector cycle complete: %s", snapshot)


async def _trader_cycle() -> None:
    """Refresh the trader leaderboard.

    This payload is tens of MB (the full Hyperliquid leaderboard), so it runs
    on its own slow interval instead of every collector tick to avoid
    repeatedly re-downloading/parsing it and delaying other collectors.
    """
    t0 = time.monotonic()
    traders = await collect_top_traders()
    logger.info("Trader cycle complete: %s traders in %.2fs", len(traders), time.monotonic() - t0)


async def _inference_cycle() -> None:
    results = await run_inference_pipeline()
    store.whale_alerts = apply_inference_to_alerts(store.whale_alerts)
    enrich_rankings_with_inference()
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
    """Run one fast collect pass so the API can start serving requests quickly.

    Two slow steps are skipped here and deferred to background loops that
    start immediately after startup (running concurrently instead of
    blocking "Application startup complete"):
    - Trader leaderboard refresh: a single HTTP call but the payload is tens
      of MB (full Hyperliquid leaderboard), taking 60-80s+ to download/parse.
      Skipped entirely if we already have traders cached from the DB.
    - Whale position collection: up to 100 clearinghouseState lookups.
    """
    t0 = time.monotonic()
    if not store.traders:
        await collect_top_traders()
        logger.info("Bootstrap: collect_top_traders (cold) took %.2fs", time.monotonic() - t0)
    else:
        logger.info(
            "Bootstrap: using %s cached traders from DB, leaderboard refresh deferred to background",
            len(store.traders),
        )
    t1 = time.monotonic()
    snapshot = await collect_market_snapshot()
    t2 = time.monotonic()
    logger.info("Bootstrap: collect_market_snapshot took %.2fs", t2 - t1)
    await collect_liquidation_events()
    t3 = time.monotonic()
    logger.info("Bootstrap: collect_liquidation_events took %.2fs", t3 - t2)
    await _ranking_cycle()
    t4 = time.monotonic()
    logger.info("Bootstrap: ranking_cycle took %.2fs", t4 - t3)
    try:
        from app.services.pulse import resolve_due_pulses

        n = resolve_due_pulses()
        logger.info("Bootstrap: pulse resolve %s (%.2fs)", n, time.monotonic() - t4)
    except Exception:
        logger.exception("Bootstrap pulse resolve failed")
    logger.info(
        "Bootstrap pipeline complete (whales/inference/alerts deferred to background): %s",
        snapshot,
    )


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
                _loop("trader_refresh", settings.trader_refresh_interval_seconds, _trader_cycle)
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
