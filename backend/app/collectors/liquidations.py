from __future__ import annotations

from app.config import settings
from app.models.schemas import LiquidationEvent
from app.services.store import store


async def collect_liquidation_events() -> list[LiquidationEvent]:
  """Report missing verified liquidation coverage without relabeling trades."""
  if settings.use_mock_data:
    # Keep existing behaviour in mock mode.
    return store.liquidation_events

  # recentTrades describes ordinary public trades, not verified liquidations.
  # Quarantine legacy events in memory; preserve DB history for operator audit.
  # A verified liquidation feed must be introduced before enabling live totals.
  store.record_collection("liquidations", 0, 1)
  with store._lock:
    store.liquidation_events = []
  return []

