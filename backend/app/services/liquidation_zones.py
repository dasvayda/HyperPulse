"""Current tracked positions grouped into 1%-of-mark liquidation price bands."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import floor, isfinite

from app.config import settings
from app.models.schemas import LiquidationZone
from app.services.liq_proximity import estimate_liquidation_px, liq_distance_pct
from app.services.store import store


def tracked_liquidation_zones(*, now=None) -> list[LiquidationZone]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=max(180, settings.collector_interval_seconds * 3))
    with store._lock:
        positions = list(store.whale_positions)
        ticks = dict(store.market_ticks)
        observed = dict(store.whale_observed_at)
    groups = defaultdict(list)
    for position in positions:
        tick = ticks.get(position.asset, {})
        mark = tick.get("mark_price")
        at = observed.get(position.trader_address.lower())
        tick_at = tick.get("updated_at")
        if not isinstance(at, datetime) or not isinstance(tick_at, datetime):
            continue
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
        tick_at = tick_at if tick_at.tzinfo else tick_at.replace(tzinfo=timezone.utc)
        if min(at, tick_at) < cutoff or max(at, tick_at) > now + timedelta(seconds=30):
            continue
        if (not isinstance(mark, (int, float)) or not isfinite(mark) or mark <= 0
                or not isfinite(position.size_usd) or position.size_usd < settings.alert_min_size_usd):
            continue
        price = position.liquidation_px
        source = "liquidationPx"
        if price is None or not isfinite(price) or price <= 0:
            source = "estimate"
            price = estimate_liquidation_px(side=position.side, entry_price=position.entry_price,
                                            leverage=position.leverage)
        if price is None or not isfinite(price) or price <= 0:
            continue
        distance = liq_distance_pct(side=position.side, mark=mark, liquidation_px=price)
        # A model already behind the mark is invalid as a forward risk level.
        if distance is None or not 0 <= distance <= 50:
            continue
        key = (position.asset, position.side.value, source, floor(distance))
        groups[key].append((position, price, min(at, tick_at)))
    zones = []
    for (asset, side, source, band), rows in groups.items():
        total = sum(position.size_usd for position, _, _ in rows)
        price = sum(position.size_usd * px for position, px, _ in rows) / total
        tick = ticks[asset]
        mark = tick["mark_price"]
        oi = float(tick.get("open_interest") or 0) * mark
        zones.append(LiquidationZone(
            id=f"tracked-{asset}-{side}-{source}-{band}", asset=asset, side=side, price=price,
            size_usd=round(total, 2), distance_pct=round((price - mark) / mark * 100, 2),
            open_interest_pct=round(total / oi * 100, 2) if oi > 0 and isfinite(oi) else 0,
            sparkline=[], source=source, positions=len(rows),
            wallets=len({position.trader_address.lower() for position, _, _ in rows}),
            observed_at=min(at for _, _, at in rows),
        ))
    return sorted(zones, key=lambda zone: (abs(zone.distance_pct), -zone.size_usd, zone.id))[:100]
