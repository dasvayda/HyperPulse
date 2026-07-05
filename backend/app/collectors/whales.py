from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from app.collectors.hyperliquid_client import info as hl_info
from app.config import settings
from app.models.schemas import AlertType, PositionSide, WhaleAlert
from app.services.store import store

logger = logging.getLogger(__name__)

# (trader_address, asset) -> current size
_LAST_SIZES: Dict[Tuple[str, str], float] = {}


def _addresses_to_track() -> list[str]:
    if not store.traders:
        return []
    addresses = [t.address for t in store.traders]
    limit = max(1, settings.tracked_trader_limit)
    return addresses[:limit]


def _extract_positions(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    positions = payload.get("assetPositions") or []
    out: list[dict] = []
    for entry in positions:
        if not isinstance(entry, dict):
            continue
        pos = entry.get("position") or {}
        if not isinstance(pos, dict):
            continue
        coin = pos.get("coin")
        szi = pos.get("szi")
        entry_px = pos.get("entryPx")
        value = pos.get("positionValue") or pos.get("position_value")
        lev = pos.get("leverage") or {}
        try:
            if not coin:
                continue
            size = float(szi)
            entry_price = float(entry_px)
            position_value = float(value)
            lev_value = lev.get("value") if isinstance(lev, dict) else None
            leverage = float(lev_value) if lev_value is not None else 1.0
        except Exception:
            continue
        out.append(
            {
                "asset": str(coin),
                "size": size,
                "entry_price": entry_price,
                "position_value": position_value,
                "leverage": leverage,
            }
        )
    return out


async def collect_whale_events() -> list[WhaleAlert]:
    """Poll clearinghouseState for tracked traders and emit WhaleAlerts on large changes."""
    if settings.use_mock_data:
        return store.whale_alerts

    addresses = _addresses_to_track()
    if not addresses:
        return store.whale_alerts

    alerts: list[WhaleAlert] = []
    traders_by_addr = {t.address: t for t in store.traders}

    for address in addresses:
        try:
            state = await hl_info({"type": "clearinghouseState", "user": address})
        except Exception as exc:
            logger.warning("clearinghouseState failed for %s: %s", address, exc)
            continue
        positions = _extract_positions(state)
        for pos in positions:
            asset = pos["asset"]
            size = pos["size"]
            key = (address, asset)

            # Approximate USD size by position value; fall back to entry_price * size.
            position_value = pos["position_value"]
            usd_size = abs(position_value)
            if usd_size < settings.alert_min_size_usd:
                _LAST_SIZES[key] = size
                continue

            # First observation seeds baseline; only later deltas emit alerts.
            if key not in _LAST_SIZES:
                _LAST_SIZES[key] = size
                continue

            prev = _LAST_SIZES[key]
            alert_type: AlertType
            if abs(prev) < 1e-6 and abs(size) >= 1e-6:
                alert_type = AlertType.ENTRY
            elif abs(prev) >= 1e-6 and abs(size) < 1e-6:
                alert_type = AlertType.EXIT
            elif prev * size < 0:
                # Direction flip treated as exit+entry; model as entry for now.
                alert_type = AlertType.ENTRY
            else:
                _LAST_SIZES[key] = size
                continue

            trader = traders_by_addr.get(address)
            alias = trader.alias if trader else f"{address[:6]}...{address[-4:]}"
            win_rate = trader.win_rate if trader else 0.0
            inferred_strategy = trader.strategy_tags[0] if trader and trader.strategy_tags else "Unknown"

            side = PositionSide.LONG if size > 0 else PositionSide.SHORT
            confidence = 75.0

            alert = WhaleAlert(
                id=store.new_id("wa"),
                trader_address=address,
                trader_alias=alias,
                asset=asset,
                side=side,
                alert_type=alert_type,
                size_usd=usd_size,
                entry_price=pos["entry_price"],
                exit_price=None,
                leverage=pos["leverage"],
                win_rate=win_rate,
                inferred_strategy=inferred_strategy,
                confidence_score=confidence,
                timestamp=store.last_collect_at or store.last_inference_at or None or __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            alerts.append(alert)
            _LAST_SIZES[key] = size

    if alerts:
        with store._lock:
            store.whale_alerts = (alerts + store.whale_alerts)[:200]
        store.persist_positions_from_alerts(alerts)
        store.refresh_dashboard()
        logger.info("Generated %s whale alerts from clearinghouseState", len(alerts))

    return store.whale_alerts

