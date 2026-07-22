from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.collectors.hyperliquid_client import info as hl_info
from app.config import settings
from app.models.schemas import LiquidationEvent, LiquidationSide
from app.services.store import store

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
  return datetime.now(timezone.utc)


def _coins_for_liquidations() -> list[str]:
  """Prefer high-volume live markets so Coin Pulse liq columns stay populated."""
  ticks = store.market_ticks or {}
  if ticks:
    ranked = sorted(
      ticks.values(),
      key=lambda t: float(t.get("day_volume_usd") or 0.0),
      reverse=True,
    )
    top = [str(t["asset"]) for t in ranked[:12]]
    if top:
      return top

  assets = {z.asset for z in store.liquidation_zones}
  if store.whale_summary and store.whale_summary.by_asset:
    heavy = sorted(
      store.whale_summary.by_asset.values(),
      key=lambda a: a.long_notional_usd + a.short_notional_usd,
      reverse=True,
    )[:8]
    assets.update(a.asset for a in heavy)
  if not assets:
    assets = {"BTC", "ETH", "SOL", "HYPE"}
  return sorted(assets)


def _valid_tx_hash(raw: Any) -> str | None:
  if not isinstance(raw, str):
    return None
  h = raw.strip().lower()
  if not h.startswith("0x") or len(h) < 10:
    return None
  if set(h[2:]) <= {"0"}:
    return None
  return raw


def _parse_recent_trades(coin: str, payload: Any) -> list[LiquidationEvent]:
  events: list[LiquidationEvent] = []
  if not isinstance(payload, list):
    return events
  for trade in payload:
    if not isinstance(trade, dict):
      continue
    try:
      px = float(trade.get("px"))
      sz = float(trade.get("sz"))
      ts = int(trade.get("time"))
    except Exception:
      continue
    side_raw = (trade.get("side") or "").upper()
    side = LiquidationSide.LONG if side_raw == "B" else LiquidationSide.SHORT
    size_usd = abs(px * sz)
    event_id = f"liq-{trade.get('tid') or trade.get('hash') or f'{coin}-{ts}'}"
    events.append(
      LiquidationEvent(
        id=event_id,
        asset=coin,
        side=side,
        size_usd=size_usd,
        price=px,
        timestamp=datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
        tx_hash=_valid_tx_hash(trade.get("hash")),
      )
    )
  return events


async def collect_liquidation_events() -> list[LiquidationEvent]:
  """Fetch recent liquidation trades for key coins from Hyperliquid Info API."""
  if settings.use_mock_data:
    # Keep existing behaviour in mock mode.
    return store.liquidation_events

  coins = _coins_for_liquidations()

  async def _fetch(coin: str) -> list[LiquidationEvent]:
    try:
      raw = await hl_info({"type": "recentTrades", "coin": coin})
    except Exception as exc:
      logger.warning("Failed to fetch recentTrades for %s: %s", coin, exc)
      return []
    return _parse_recent_trades(coin, raw)

  results = await asyncio.gather(*[_fetch(coin) for coin in coins])
  all_events: list[LiquidationEvent] = [event for batch in results for event in batch]

  if not all_events:
    return store.liquidation_events

  unique: dict[str, LiquidationEvent] = {}
  for event in all_events:
    unique[event.id] = event
  merged = sorted(unique.values(), key=lambda e: e.timestamp, reverse=True)[:200]

  with store._lock:
    store.liquidation_events = merged
  store.persist_liquidations(merged)
  store.refresh_dashboard()
  logger.info("Collected %s liquidation events", len(merged))
  return store.liquidation_events

