from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from app.collectors.hyperliquid_client import info as hl_info
from app.config import settings
from app.models.schemas import AlertType, PositionSide, WhaleAlert
from app.models.schemas import OpenPosition, WhalePosition
from app.db import SessionLocal
from app.models.orm import MarketSnapshotRow
from app.services.fresh_entries import classify_size_change
from app.services.store import store, _position_roi

logger = logging.getLogger(__name__)

# (trader_address, asset) -> current coin size / notional
_LAST_SIZES: Dict[Tuple[str, str], float] = {}
_LAST_USD: Dict[Tuple[str, str], float] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
                "unrealized_pnl": _safe_float(pos.get("unrealizedPnl") or pos.get("unrealized_pnl")),
            }
        )
    return out


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


async def fetch_live_positions(
    address: str,
    *,
    update_store: bool = True,
) -> list[WhalePosition]:
    """Fetch current open positions from Hyperliquid clearinghouseState.

    Used by trader detail so the UI is not stuck on a stale whale-book cache.
    On failure, falls back to whatever is already in the in-memory whale book.
    """
    if settings.use_mock_data:
        return store.get_open_positions(address)

    try:
        state = await hl_info({"type": "clearinghouseState", "user": address})
    except Exception as exc:
        logger.warning("live clearinghouseState failed for %s: %s", address, exc)
        return store.get_open_positions(address)

    if state is None:
        return store.get_open_positions(address)

    positions: list[WhalePosition] = []
    for pos in _extract_positions(state):
        size = pos["size"]
        if abs(size) < 1e-12:
            continue
        positions.append(
            WhalePosition(
                trader_address=address,
                asset=pos["asset"],
                side=PositionSide.LONG if size > 0 else PositionSide.SHORT,
                size_usd=abs(float(pos["position_value"])),
                entry_price=float(pos["entry_price"]),
                leverage=float(pos["leverage"] or 1.0),
            )
        )

    if update_store:
        store.upsert_trader_positions(address, positions)
    return positions


async def fetch_live_open_positions(address: str) -> list[OpenPosition]:
    """Live clearinghouse positions enriched with mark / ROI for trader detail."""
    from app.services.store import _latest_mark_prices, _position_roi

    if settings.use_mock_data:
        detail = store.get_trader_detail(address)
        return detail.open_positions if detail else []

    try:
        state = await hl_info({"type": "clearinghouseState", "user": address})
    except Exception as exc:
        logger.warning("live clearinghouseState failed for %s: %s", address, exc)
        return []

    if not isinstance(state, dict):
        return []

    raw = _extract_positions(state)
    whale_positions: list[WhalePosition] = []
    assets = {str(p["asset"]) for p in raw}
    marks = _latest_mark_prices(assets)
    open_positions: list[OpenPosition] = []

    for pos in sorted(raw, key=lambda p: abs(float(p["position_value"])), reverse=True):
        size = float(pos["size"])
        if abs(size) < 1e-12:
            continue
        asset = str(pos["asset"])
        size_usd = abs(float(pos["position_value"]))
        entry = float(pos["entry_price"])
        leverage = float(pos["leverage"] or 1.0)
        side = PositionSide.LONG if size > 0 else PositionSide.SHORT
        implied_mark = abs(float(pos["position_value"]) / size)
        mark = marks.get(asset) or implied_mark
        roi_pct, unrealized = _position_roi(
            side=side,
            entry_price=entry,
            mark_price=mark,
            size_usd=size_usd,
            leverage=leverage,
        )
        if unrealized is None and pos.get("unrealized_pnl") is not None:
            unrealized = round(float(pos["unrealized_pnl"]), 2)

        whale_positions.append(
            WhalePosition(
                trader_address=address,
                asset=asset,
                side=side,
                size_usd=size_usd,
                entry_price=entry,
                leverage=leverage,
            )
        )
        open_positions.append(
            OpenPosition(
                asset=asset,
                side=side,
                size_usd=size_usd,
                entry_price=entry,
                leverage=leverage,
                mark_price=round(mark, 6) if mark else None,
                roi_pct=roi_pct,
                unrealized_pnl_usd=unrealized,
            )
        )

    store.upsert_trader_positions(address, whale_positions)
    return open_positions


def _latest_mark_price(asset: str) -> float | None:
    db = SessionLocal()
    try:
        row = (
            db.query(MarketSnapshotRow)
            .filter(MarketSnapshotRow.asset == asset)
            .order_by(MarketSnapshotRow.timestamp.desc())
            .first()
        )
        return float(row.mark_price) if row else None
    finally:
        db.close()


async def _fetch_clearinghouse_state(
    address: str, semaphore: asyncio.Semaphore
) -> tuple[str, Any]:
    async with semaphore:
        try:
            state = await hl_info({"type": "clearinghouseState", "user": address})
        except Exception as exc:
            logger.warning("clearinghouseState failed for %s: %s", address, exc)
            return address, None
        return address, state


async def collect_whale_events() -> list[WhaleAlert]:
    """Poll clearinghouseState for tracked traders and emit WhaleAlerts on large changes."""
    if settings.use_mock_data:
        return store.whale_alerts

    addresses = _addresses_to_track()
    if not addresses:
        return store.whale_alerts

    alerts: list[WhaleAlert] = []
    positions_snapshot: list[WhalePosition] = []
    traders_by_addr = {t.address: t for t in store.traders}

    # Fetch concurrently (bounded) instead of one-by-one: sequential requests for
    # 100 tracked addresses were the dominant cause of slow startup/collect cycles.
    semaphore = asyncio.Semaphore(max(1, settings.whale_fetch_concurrency))
    results = await asyncio.gather(
        *[_fetch_clearinghouse_state(address, semaphore) for address in addresses]
    )

    for address, state in results:
        if state is None:
            continue
        positions = _extract_positions(state)
        for pos in positions:
            asset = pos["asset"]
            size = pos["size"]
            key = (address, asset)

            # Approximate USD size by position value; fall back to entry_price * size.
            position_value = pos["position_value"]
            usd_size = abs(position_value)

            positions_snapshot.append(
                WhalePosition(
                    trader_address=address,
                    asset=asset,
                    side=PositionSide.LONG if size > 0 else PositionSide.SHORT,
                    size_usd=usd_size,
                    entry_price=pos["entry_price"],
                    leverage=pos["leverage"],
                )
            )

            if usd_size < settings.alert_min_size_usd:
                _LAST_SIZES[key] = size
                _LAST_USD[key] = usd_size
                continue

            # First observation seeds baseline; only later deltas emit alerts.
            if key not in _LAST_SIZES:
                _LAST_SIZES[key] = size
                _LAST_USD[key] = usd_size
                continue

            prev = _LAST_SIZES[key]
            prev_usd = _LAST_USD.get(key, 0.0)
            min_add = settings.alert_min_size_usd * 0.5
            alert_type, size_delta_usd = classify_size_change(
                prev, size, prev_usd, usd_size, min_add
            )
            if alert_type is None:
                _LAST_SIZES[key] = size
                _LAST_USD[key] = usd_size
                continue

            trader = traders_by_addr.get(address)
            alias = trader.alias if trader else f"{address[:6]}...{address[-4:]}"
            win_rate = trader.win_rate if trader else 0.0
            inference = store.get_inference(address)
            if inference:
                inferred_strategy = inference.strategy
            elif trader and trader.strategy_tags:
                inferred_strategy = trader.strategy_tags[0]
            else:
                # Avoid "Unknown" at collect time (BL-05) — same heuristic as apply_inference_to_alerts.
                avg_lev = (
                    sum(float(p["leverage"]) for p in positions) / len(positions)
                    if positions
                    else float(pos["leverage"] or 1.0)
                )
                if avg_lev >= 20:
                    inferred_strategy = "Speculative"
                elif len(positions) == 1:
                    inferred_strategy = "Directional"
                elif len(positions) >= 4:
                    inferred_strategy = "Diversified"
                else:
                    inferred_strategy = "Mixed"

            side = PositionSide.LONG if size > 0 else PositionSide.SHORT
            confidence = 75.0

            exit_price = None
            if alert_type == AlertType.EXIT:
                exit_price = _latest_mark_price(asset)

            # BL-05 enrich: mark / uPnL / ROI / book long% (HL provenance).
            mark_price = _latest_mark_price(asset)
            if mark_price is None and abs(size) > 1e-12:
                mark_price = abs(float(pos["position_value"]) / size)
            roi_pct = None
            unrealized_pnl_usd = pos.get("unrealized_pnl")
            if mark_price is not None and pos["entry_price"]:
                roi_pct, upnl_calc = _position_roi(
                    side=side,
                    entry_price=float(pos["entry_price"]),
                    mark_price=float(mark_price),
                    size_usd=usd_size,
                    leverage=float(pos["leverage"] or 1.0),
                )
                if unrealized_pnl_usd is None:
                    unrealized_pnl_usd = upnl_calc
            whale_long_pct = None
            if store.whale_summary and asset in store.whale_summary.by_asset:
                whale_long_pct = store.whale_summary.by_asset[asset].long_pct

            alert = WhaleAlert(
                id=store.new_id("wa"),
                trader_address=address,
                trader_alias=alias,
                asset=asset,
                side=side,
                alert_type=alert_type,
                size_usd=usd_size,
                size_delta_usd=size_delta_usd,
                entry_price=pos["entry_price"],
                exit_price=exit_price,
                mark_price=mark_price,
                unrealized_pnl_usd=unrealized_pnl_usd,
                roi_pct=roi_pct,
                whale_long_pct=whale_long_pct,
                leverage=pos["leverage"],
                win_rate=win_rate,
                inferred_strategy=inferred_strategy,
                confidence_score=confidence,
                timestamp=store.last_collect_at or store.last_inference_at or _utcnow(),
            )
            alerts.append(alert)
            _LAST_SIZES[key] = size
            _LAST_USD[key] = usd_size

    store.update_whale_book(positions_snapshot, updated_at=store.last_collect_at or _utcnow())

    if alerts:
        with store._lock:
            store.whale_alerts = (alerts + store.whale_alerts)[:200]
        store.persist_positions_from_alerts(alerts)
        store.refresh_dashboard()
        logger.info("Generated %s whale alerts from clearinghouseState", len(alerts))

    return store.whale_alerts

