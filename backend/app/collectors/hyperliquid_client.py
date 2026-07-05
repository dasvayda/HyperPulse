from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


async def info(request: dict) -> Any:
    """Call Hyperliquid Info API (POST /info)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{settings.hyperliquid_api_url.rstrip('/')}/info",
            json=request,
        )
        resp.raise_for_status()
        return resp.json()


async def stats(endpoint: str) -> Any:
    """Call Hyperliquid stats API (leaderboard, vaults, ...)."""
    base = settings.hyperliquid_stats_url.rstrip("/")
    url = f"{base}/{endpoint.lstrip('/')}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

