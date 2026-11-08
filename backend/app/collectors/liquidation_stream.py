"""Opt-in bounded stream. No REST sweep and no market-pressure publication."""
from __future__ import annotations

import asyncio
import json
import logging

from app.config import settings
from app.services.verified_liquidations import coverage_start, coverage_touch, ingest, watch_addresses

logger = logging.getLogger(__name__)


async def run_liquidation_stream():
    from websockets.asyncio.client import connect

    roster = watch_addresses()  # Invalid budgets fail before opening a connection.
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
                        else:
                            raise TimeoutError("Subscription initialization incomplete")
                        continue
                    message = json.loads(raw)
                    if message.get("channel") == "error":
                        raise ValueError("Subscription rejected")
                    if message.get("channel") != "userFills":
                        continue
                    data = message["data"]
                    wallet = str(data.get("user", "")).lower()
                    if wallet not in roster or not isinstance(data.get("fills"), list):
                        raise ValueError("Unexpected user fills envelope")
                    _, rejected = await asyncio.to_thread(ingest, wallet, data["fills"])
                    if rejected:
                        raise ValueError("Ambiguous liquidation payload quarantined")
                    if data.get("isSnapshot") is True:
                        initialized.add(wallet)
                    if key:
                        await asyncio.to_thread(coverage_touch, key)
                    elif initialized == set(roster):
                        key = await asyncio.to_thread(coverage_start, roster)
                        delay = 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # No raw messages or URLs in the log.
            logger.warning("Liquidation stream interrupted: %s", type(exc).__name__)
        finally:
            if key:
                try:
                    await asyncio.to_thread(coverage_touch, key, end="stream_gap")
                except Exception as exc:
                    # DB outage must not kill the reconnect loop. A stale
                    # heartbeat already makes coverage unavailable to readers.
                    logger.warning("Liquidation coverage close failed: %s", type(exc).__name__)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)
