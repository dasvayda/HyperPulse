"""Opt-in bounded stream. No REST sweep and no market-pressure publication."""
from __future__ import annotations

import asyncio
import json
import logging

from app.config import settings
from app.services.verified_liquidations import coverage_start, coverage_touch, ingest, watch_addresses
from app.services.store import store

logger = logging.getLogger(__name__)


class LiquidationStreamError(ValueError):
    """Only fixed internal reason codes may be exposed in runtime logs."""


async def run_liquidation_stream():
    from websockets.asyncio.client import connect

    roster = watch_addresses()  # Invalid budgets fail before opening a connection.
    store.record_collection("watched_liquidations", 0, len(roster))
    delay = 1
    while True:
        key = None
        try:
            async with connect(settings.hyperliquid_ws_url, open_timeout=10, close_timeout=5,
                               ping_interval=20, ping_timeout=10, max_size=4 * 1024 * 1024) as ws:
                for wallet in roster:
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {
                        "type": "userFills", "user": wallet, "aggregateByTime": False}}))
                initialized = set()
                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=15)
                    except asyncio.TimeoutError:
                        pong = await ws.ping()
                        await asyncio.wait_for(pong, timeout=10)
                        if key:
                            await asyncio.to_thread(coverage_touch, key)
                            store.record_collection("watched_liquidations", len(roster), len(roster))
                        else:
                            raise TimeoutError("Subscription initialization incomplete")
                        continue
                    message = json.loads(raw)
                    if message.get("channel") == "error":
                        raise LiquidationStreamError("subscription_rejected")
                    if message.get("channel") != "userFills":
                        continue
                    data = message["data"]
                    wallet = str(data.get("user", "")).lower()
                    if wallet not in roster or not isinstance(data.get("fills"), list):
                        raise LiquidationStreamError("unexpected_fills_envelope")
                    _, rejected = await asyncio.to_thread(ingest, wallet, data["fills"])
                    if rejected:
                        raise LiquidationStreamError("ambiguous_liquidation_quarantined")
                    if data.get("isSnapshot") is True:
                        initialized.add(wallet)
                    if key:
                        await asyncio.to_thread(coverage_touch, key)
                        store.record_collection("watched_liquidations", len(roster), len(roster))
                    elif initialized == set(roster):
                        key = await asyncio.to_thread(coverage_start, roster)
                        store.record_collection("watched_liquidations", len(roster), len(roster))
                        logger.info("Liquidation watch initialized: %d fixed wallets", len(roster))
                        delay = 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # No raw messages or URLs in the log.
            reason = str(exc) if isinstance(exc, LiquidationStreamError) else type(exc).__name__
            logger.warning("Liquidation stream interrupted: %s", reason)
        finally:
            store.record_collection("watched_liquidations", 0, len(roster))
            if key:
                try:
                    await asyncio.to_thread(coverage_touch, key, end="stream_gap")
                except Exception as exc:
                    # DB outage must not kill the reconnect loop. A stale
                    # heartbeat already makes coverage unavailable to readers.
                    logger.warning("Liquidation coverage close failed: %s", type(exc).__name__)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)
