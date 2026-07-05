from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from app.collectors.hyperliquid_client import info as hl_info
from app.config import settings
from app.db import SessionLocal
from app.models.orm import MarketSnapshotRow
from app.models.schemas import (
    AlertType,
    LiquidationEvent,
    LiquidationSide,
    LiquidationZone,
    PositionSide,
    TraderProfile,
    WhaleAlert,
)
from app.services.cache import cache_get, cache_set
from app.services.store import store

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def fetch_meta_and_asset_ctxs() -> dict | None:
    cache_key = "hl:meta_asset_ctxs"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        data = await hl_info({"type": "metaAndAssetCtxs"})
        cache_set(cache_key, data, ttl_seconds=30)
        return data
    except Exception as exc:
        logger.warning("Hyperliquid meta fetch failed: %s", exc)
        return None


def _simulate_market_tick() -> None:
    """Advance seed-based state when live API is unavailable."""
    now = _utcnow()
    traders: list[TraderProfile] = []
    for trader in store.traders:
        drift = random.uniform(-1.2, 1.8)
        spark = list(trader.sparkline[1:] + [max(1.0, trader.sparkline[-1] + drift)])
        traders.append(
            trader.model_copy(
                update={
                    "pnl_change_pct": round(trader.pnl_change_pct + drift * 0.15, 2),
                    "pnl_usd": max(0.0, trader.pnl_usd * (1 + drift / 500)),
                    "sparkline": [round(v, 1) for v in spark],
                }
            )
        )
    store.traders = traders

    zones: list[LiquidationZone] = []
    for zone in store.liquidation_zones:
        spark = list(zone.sparkline[1:] + [max(1.0, zone.sparkline[-1] + random.uniform(-3, 4))])
        zones.append(
            zone.model_copy(
                update={
                    "size_usd": max(1_000_000.0, zone.size_usd * (1 + random.uniform(-0.02, 0.03))),
                    "sparkline": [round(v, 1) for v in spark],
                }
            )
        )
    store.liquidation_zones = zones

    # Occasionally inject a fresh whale alert
    if random.random() < 0.35 and store.traders:
        trader = random.choice(store.traders)
        asset = random.choice(trader.preferred_assets or ["BTC"])
        side = random.choice([PositionSide.LONG, PositionSide.SHORT])
        alert_type = random.choice([AlertType.ENTRY, AlertType.EXIT])
        size = random.uniform(400_000, 4_500_000)
        alert = WhaleAlert(
            id=store.new_id("wa"),
            trader_address=trader.address,
            trader_alias=trader.alias,
            asset=asset,
            side=side,
            alert_type=alert_type,
            size_usd=round(size, 0),
            entry_price=round(random.uniform(20, 100_000), 2) if alert_type == AlertType.ENTRY else None,
            exit_price=round(random.uniform(20, 100_000), 2) if alert_type == AlertType.EXIT else None,
            leverage=round(random.uniform(3, 15), 1),
            win_rate=trader.win_rate,
            inferred_strategy=trader.strategy_tags[0] if trader.strategy_tags else "Mixed",
            confidence_score=round(random.uniform(60, 92), 1),
            timestamp=now - timedelta(minutes=random.randint(1, 20)),
        )
        store.whale_alerts.insert(0, alert)
        store.whale_alerts = store.whale_alerts[:50]

    if random.random() < 0.4:
        asset = random.choice(["BTC", "ETH", "SOL", "HYPE"])
        event = LiquidationEvent(
            id=store.new_id("le"),
            asset=asset,
            side=random.choice([LiquidationSide.LONG, LiquidationSide.SHORT]),
            size_usd=round(random.uniform(80_000, 2_500_000), 0),
            price=round(random.uniform(20, 100_000), 2),
            timestamp=now - timedelta(minutes=random.randint(1, 30)),
        )
        store.liquidation_events.insert(0, event)
        store.liquidation_events = store.liquidation_events[:50]


def _apply_live_meta(data: list | dict) -> None:
    """Anchor liquidation zones around live mark prices."""
    try:
        meta, contexts = data[0], data[1]
        universe = meta.get("universe", [])
        price_map: dict[str, float] = {}
        for idx, ctx in enumerate(contexts):
            name = universe[idx].get("name") if idx < len(universe) else None
            mark = ctx.get("markPx")
            if name and mark:
                price_map[name] = float(mark)

        # Keep relative offsets stable per asset side so zones track the market.
        offsets: dict[tuple[str, str], float] = {}
        for zone in store.liquidation_zones:
            key = (zone.asset, zone.side.value)
            if key not in offsets:
                offsets[key] = abs(zone.distance_pct) or 4.0

        updated_zones: list[LiquidationZone] = []
        for zone in store.liquidation_zones:
            mark = price_map.get(zone.asset)
            if mark and mark > 0:
                offset = offsets[(zone.asset, zone.side.value)]
                if zone.side.value == "short":
                    price = mark * (1 + offset / 100)
                    distance = offset
                else:
                    price = mark * (1 - offset / 100)
                    distance = -offset
                updated_zones.append(
                    zone.model_copy(
                        update={
                            "price": round(price, 2),
                            "distance_pct": round(distance, 2),
                        }
                    )
                )
            else:
                updated_zones.append(zone)
        store.liquidation_zones = updated_zones

        if price_map:
            # Prefer major assets for dashboard top asset label.
            for preferred in ("BTC", "ETH", "SOL", "HYPE"):
                if preferred in price_map:
                    store.dashboard = store.dashboard.model_copy(
                        update={"top_asset": preferred}
                    )
                    break
    except Exception as exc:
        logger.warning("Failed applying live meta: %s", exc)


async def collect_market_snapshot() -> dict:
    live = await fetch_meta_and_asset_ctxs()
    source = "hyperliquid" if live is not None else "simulated"

    if live is not None:
        _apply_live_meta(live)
        # Persist basic market snapshot for later analytics
        try:
            meta, contexts = live[0], live[1]
            universe = meta.get("universe", [])
            db = SessionLocal()
            now = _utcnow()
            for idx, ctx in enumerate(contexts):
                name = universe[idx].get("name") if idx < len(universe) else None
                if not name:
                    continue
                mark = ctx.get("markPx")
                if mark is None:
                    continue
                oi = ctx.get("openInterest") or ctx.get("openInterest", "0")
                funding = ctx.get("funding") or "0"
                snapshot = MarketSnapshotRow(
                    asset=name,
                    mark_price=float(mark),
                    open_interest=float(oi),
                    funding_rate=float(funding),
                    timestamp=now,
                )
                db.add(snapshot)
            db.commit()
            db.close()
        except Exception as exc:
            logger.warning("Failed to persist market snapshot: %s", exc)
    elif settings.use_mock_data:
        _simulate_market_tick()

    with store._lock:
        store.last_collect_at = _utcnow()

    store.persist_traders(store.traders)
    store.persist_liquidations(store.liquidation_events)
    store.persist_positions_from_alerts(store.whale_alerts)
    store.refresh_dashboard()

    snapshot = {
        "source": source,
        "traders": len(store.traders),
        "alerts": len(store.whale_alerts),
        "zones": len(store.liquidation_zones),
        "collected_at": store.last_collect_at.isoformat() if store.last_collect_at else None,
    }
    cache_set("hl:last_snapshot", snapshot, ttl_seconds=120)
    return snapshot
