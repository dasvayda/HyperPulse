"""CMC Crypto Fear and Greed Index (keyless public API).

Docs: https://coinmarketcap.com/api/documentation/pro-api-reference/keyless-public-api
Page: https://coinmarketcap.com/charts/fear-and-greed-index/

Keyless public endpoints (no API key):
  GET https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/latest
  GET https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/historical?limit=2

Pro key (optional, higher limits):
  GET https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest
  Header: X-CMC_PRO_API_KEY
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.models.schemas import FearGreedIndex
from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

CACHE_KEY = "cmc:fear_greed:v1"
CACHE_TTL_SEC = 1800  # 30m — slow-moving index; avoid CMC public rate limits


def _latest_url() -> str:
    if settings.cmc_api_key:
        return "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"
    return "https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/latest"


def _historical_url() -> str:
    if settings.cmc_api_key:
        return "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
    return "https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/historical"


def _headers() -> dict[str, str]:
    if settings.cmc_api_key:
        return {"X-CMC_PRO_API_KEY": settings.cmc_api_key}
    return {}


def _parse_ts(raw) -> datetime | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.isdigit()):
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError, OSError):
        return None


def _tone(classification: str) -> bool | None:
    c = classification.lower()
    if "fear" in c:
        return False
    if "greed" in c:
        return True
    return None


def _from_cache() -> FearGreedIndex | None:
    cached = cache_get(CACHE_KEY)
    if isinstance(cached, dict) and "value" in cached:
        try:
            return FearGreedIndex.model_validate(cached)
        except Exception:
            return None
    return None


async def fetch_fear_greed(*, force: bool = False) -> FearGreedIndex | None:
    if not force:
        hit = _from_cache()
        if hit is not None:
            return hit

    headers = _headers()
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
            latest_r = await client.get(_latest_url())
            if latest_r.status_code == 429:
                logger.warning("CMC Fear & Greed rate-limited (429); using cache if any")
                return _from_cache()
            latest_r.raise_for_status()
            latest = latest_r.json().get("data") or {}

            yesterday_value: int | None = None
            yesterday_classification: str | None = None
            hist_r = await client.get(_historical_url(), params={"limit": 2})
            if hist_r.status_code == 200:
                hist = hist_r.json().get("data") or []
                if isinstance(hist, list) and len(hist) >= 2:
                    y = hist[1]
                    try:
                        yesterday_value = int(y.get("value"))
                        yesterday_classification = str(y.get("value_classification") or "") or None
                    except (TypeError, ValueError):
                        pass
            elif hist_r.status_code == 429:
                logger.warning("CMC F&G historical rate-limited; latest only")
    except Exception as exc:
        logger.warning("CMC Fear & Greed fetch failed: %s", exc)
        return _from_cache()

    try:
        value = int(latest.get("value") or 0)
    except (TypeError, ValueError):
        return _from_cache()

    classification = str(latest.get("value_classification") or "Neutral")
    as_of = _parse_ts(latest.get("update_time")) or datetime.now(timezone.utc)

    item = FearGreedIndex(
        value=value,
        classification=classification,
        as_of=as_of,
        yesterday_value=yesterday_value,
        yesterday_classification=yesterday_classification,
        source="cmc",
        positive=_tone(classification),
    )
    cache_set(CACHE_KEY, item.model_dump(mode="json"), CACHE_TTL_SEC)
    return item
