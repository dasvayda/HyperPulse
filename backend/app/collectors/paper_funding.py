"""Bounded public rate history for the three paper assets; no wallet sweep."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from app.collectors.hyperliquid_client import info
from app.config import settings
from app.db import SessionLocal
from app.models.orm import PaperFundingRateRow, PaperRunStateRow, PaperStrategyRow

logger = logging.getLogger(__name__)
_last_attempt: datetime | None = None


async def collect_paper_funding(at: datetime | None = None) -> None:
    global _last_attempt
    if settings.use_mock_data or not settings.paper_portfolio_enabled:
        return
    now = at or datetime.now(timezone.utc)
    if _last_attempt and (now - _last_attempt).total_seconds() < 60:
        return
    _last_attempt = now
    from app.services.paper_portfolio import ASSETS, STRATEGY_ID
    from app.services.paper_forward import aware
    with SessionLocal() as db:
        strategy = db.get(PaperStrategyRow, STRATEGY_ID)
        start = aware(strategy.started_at) if strategy else now - timedelta(hours=1)
        state = db.get(PaperRunStateRow, STRATEGY_ID)
        if state:
            start = max(start, aware(state.funding_through).replace(minute=0, second=0, microsecond=0))
    for asset in ASSETS:
        try:
            with SessionLocal() as db:
                latest = db.query(PaperFundingRateRow).filter(PaperFundingRateRow.asset == asset).order_by(PaperFundingRateRow.funded_at.desc()).first()
                # Inclusive overlap deduplicates hourly records, including delayed settlements.
                since = min(start, aware(latest.funded_at) - timedelta(hours=1)) if latest else start
            data = await info({"type": "fundingHistory", "coin": asset,
                               "startTime": int(since.timestamp() * 1000), "endTime": int(now.timestamp() * 1000)})
            with SessionLocal() as db:
                if not isinstance(data, list):
                    raise ValueError("Invalid funding envelope")
                for item in data:
                    if not isinstance(item, dict) or isinstance(item.get("time"), bool) or isinstance(item.get("fundingRate"), bool):
                        raise ValueError("Invalid funding record")
                    when = datetime.fromtimestamp(int(item["time"]) / 1000, tz=timezone.utc)
                    rate = float(item["fundingRate"])
                    if item.get("coin") != asset or not math.isfinite(rate) or not since <= when <= now or when.minute or when.second or when.microsecond:
                        raise ValueError("Invalid funding record")
                    key = f"{asset}:{int(when.timestamp())}"
                    if not db.get(PaperFundingRateRow, key):
                        db.add(PaperFundingRateRow(id=key, asset=asset, funded_at=when, rate=rate, received_at=now))
                        db.flush()
                db.commit()
        except Exception as exc:
            logger.warning("Paper funding unavailable for %s: %s", asset, type(exc).__name__)
