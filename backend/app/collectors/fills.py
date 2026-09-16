"""BL-09: recent executed flow (userFillsByTime) for tracked traders.

Rate-limit posture: this is fetched on demand for a single trader (detail page)
and cached, never swept across the whole tracked universe on a timer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.collectors.hyperliquid_client import info as hl_info
from app.config import settings
from app.models.schemas import (
    OpenPosition,
    PositionSide,
    TraderFillAsset,
    TraderFillsSummary,
)
from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

FILLS_CACHE_TTL_SECONDS = 180
FILLS_WINDOW_HOURS = 24


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def position_check_line(
    summary: TraderFillsSummary,
    open_positions: list[OpenPosition] | None,
) -> str | None:
    """One line tying 24h flow back to what the trader still holds."""
    if not summary.top_asset or summary.fills == 0:
        return None
    asset = summary.top_asset
    row = next((a for a in summary.assets if a.asset == asset), None)
    if row is None:
        return None

    held = next(
        (p for p in (open_positions or []) if p.asset.upper() == asset.upper()),
        None,
    )
    if held is None:
        return f"No open {asset} position left after this flow"

    side = held.side.value if isinstance(held.side, PositionSide) else str(held.side)
    if row.net_usd == 0:
        return f"{asset} flow is two-way; still holds the {side}"
    buying = row.net_usd > 0
    aligned = (side == "long" and buying) or (side == "short" and not buying)
    if aligned:
        return f"Adding to the open {asset} {side}"
    return f"Trimming the open {asset} {side}"


def summarize_fills(
    raw: list[dict],
    *,
    now: datetime | None = None,
    window_hours: int = FILLS_WINDOW_HOURS,
) -> TraderFillsSummary:
    """Aggregate raw HL fills into buy/sell notional per coin.

    HL fill shape: {coin, px, sz, side: "B"|"A", time (ms), closedPnl, dir}.
    """
    now = now or _utcnow()
    cutoff_ms = (now - timedelta(hours=window_hours)).timestamp() * 1000.0

    buckets: dict[str, dict[str, float]] = {}
    buy_usd = 0.0
    sell_usd = 0.0
    realized = 0.0
    count = 0
    last_ms: float | None = None

    for fill in raw:
        if not isinstance(fill, dict):
            continue
        ts = _safe_float(fill.get("time"))
        if ts is None or ts < cutoff_ms:
            continue
        px = _safe_float(fill.get("px"))
        sz = _safe_float(fill.get("sz"))
        coin = fill.get("coin")
        if px is None or sz is None or not coin:
            continue
        notional = abs(px * sz)
        if notional <= 0:
            continue
        asset = str(coin)
        bucket = buckets.setdefault(asset, {"buy": 0.0, "sell": 0.0, "fills": 0.0})
        # HL marks the taker direction as "B" (buy) or "A" (ask/sell).
        is_buy = str(fill.get("side") or "").upper().startswith("B")
        if is_buy:
            bucket["buy"] += notional
            buy_usd += notional
        else:
            bucket["sell"] += notional
            sell_usd += notional
        bucket["fills"] += 1
        count += 1
        realized += _safe_float(fill.get("closedPnl")) or 0.0
        last_ms = ts if last_ms is None else max(last_ms, ts)

    assets = [
        TraderFillAsset(
            asset=asset,
            buy_usd=round(data["buy"], 2),
            sell_usd=round(data["sell"], 2),
            net_usd=round(data["buy"] - data["sell"], 2),
            fills=int(data["fills"]),
        )
        for asset, data in buckets.items()
    ]
    assets.sort(key=lambda a: a.buy_usd + a.sell_usd, reverse=True)

    last_fill_at = None
    if last_ms is not None:
        last_fill_at = datetime.fromtimestamp(last_ms / 1000.0, tz=timezone.utc)

    return TraderFillsSummary(
        window_hours=window_hours,
        fills=count,
        buy_usd=round(buy_usd, 2),
        sell_usd=round(sell_usd, 2),
        net_usd=round(buy_usd - sell_usd, 2),
        realized_pnl_usd=round(realized, 2),
        assets=assets[:5],
        top_asset=assets[0].asset if assets else None,
        last_fill_at=last_fill_at,
    )


async def fetch_recent_fills(
    address: str,
    *,
    window_hours: int = FILLS_WINDOW_HOURS,
    open_positions: list[OpenPosition] | None = None,
) -> TraderFillsSummary | None:
    """Last-24h executed flow for one tracked address (cached, on demand)."""
    if settings.use_mock_data:
        return None

    now = _utcnow()
    cache_key = f"hl:fills:{address.lower()}:{window_hours}"
    cached = cache_get(cache_key)
    raw: list[dict] | None = None
    if isinstance(cached, list):
        raw = cached
    else:
        start_ms = int((now - timedelta(hours=window_hours)).timestamp() * 1000)
        try:
            data = await hl_info(
                {
                    "type": "userFillsByTime",
                    "user": address,
                    "startTime": start_ms,
                }
            )
        except Exception as exc:
            logger.warning("userFillsByTime failed for %s: %s", address, exc)
            return None
        if not isinstance(data, list):
            return None
        raw = [f for f in data if isinstance(f, dict)]
        cache_set(cache_key, raw, ttl_seconds=FILLS_CACHE_TTL_SECONDS)

    summary = summarize_fills(raw or [], now=now, window_hours=window_hours)
    summary.position_check = position_check_line(summary, open_positions)
    return summary
