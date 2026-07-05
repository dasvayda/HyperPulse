from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.models.schemas import (
    AlertHistoryItem,
    LiquidationZone,
    StrategyInference,
    WhaleAlert,
)
from app.services.store import store

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _send_telegram(message: str) -> bool:
    if not settings.telegram_configured:
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


def _record_alert(
    event_type: str,
    title: str,
    message: str,
    status: str,
    payload: dict | None = None,
) -> AlertHistoryItem:
    now = _utcnow()
    item = AlertHistoryItem(
        id=store.new_id("al"),
        channel="telegram",
        event_type=event_type,
        title=title,
        message=message,
        status=status,
        created_at=now,
        sent_at=now if status == "sent" else None,
    )
    with store._lock:
        store.alerts.insert(0, item)
        store.alerts = store.alerts[:100]
        store.last_alert_at = now
    store.persist_alert(item, payload)
    store.refresh_dashboard()
    return item


def _is_recent_duplicate(
    event_type: str,
    title: str,
    message: str,
    max_age_seconds: int = 3600,
) -> bool:
    """Return True if an identical alert was recently created."""
    cutoff = _utcnow() - timedelta(seconds=max_age_seconds)
    # store.alerts is sorted newest first
    for existing in store.alerts:
        created_at = existing.created_at
        # Normalize to aware UTC to avoid naive/aware comparison issues
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        try:
            if created_at < cutoff:
                break
        except TypeError:
            # If comparison still fails for some reason, skip this record
            continue

        if (
            existing.event_type == event_type
            and existing.title == title
            and existing.message == message
            and existing.status in {"sent", "queued"}
        ):
            return True
    return False


async def send_whale_alert(alert: WhaleAlert) -> AlertHistoryItem | None:
    if not settings.alerts_enabled:
        return None
    if alert.confidence_score < settings.alert_min_confidence:
        return None
    if alert.size_usd < settings.alert_min_size_usd:
        return None

    title = f"Whale {alert.alert_type.value.upper()} - {alert.asset}"
    message = (
        f"<b>{title}</b>\n"
        f"Trader: {alert.trader_alias} ({alert.trader_address})\n"
        f"Side: {alert.side.value.upper()} | Size: ${alert.size_usd:,.0f}\n"
        f"Leverage: {alert.leverage}x | Win rate: {alert.win_rate}%\n"
        f"Strategy: {alert.inferred_strategy} ({alert.confidence_score:.0f}% conf)"
    )
    plain = message.replace("<b>", "").replace("</b>", "")
    event_type = f"whale_{alert.alert_type.value}"
    if _is_recent_duplicate(event_type, title, plain):
        return None

    sent = await _send_telegram(message)
    status = "sent" if sent else ("queued" if not settings.telegram_configured else "failed")
    return _record_alert(
        event_type=event_type,
        title=title,
        message=plain,
        status=status,
        payload=alert.model_dump(mode="json"),
    )


async def send_squeeze_alert(zone: LiquidationZone) -> AlertHistoryItem | None:
    if not settings.alerts_enabled:
        return None
    if zone.size_usd < 100_000_000:
        return None

    title = f"Squeeze risk - {zone.asset}"
    message = (
        f"<b>{title}</b>\n"
        f"{zone.side.value.upper()} liquidation zone at ${zone.price:,.0f}\n"
        f"Size: ${zone.size_usd / 1_000_000:.0f}M | Distance: {zone.distance_pct:+.1f}%\n"
        f"OI share: {zone.open_interest_pct:.1f}%"
    )
    plain = message.replace("<b>", "").replace("</b>", "")
    event_type = "squeeze_risk"
    if _is_recent_duplicate(event_type, title, plain):
        return None

    sent = await _send_telegram(message)
    status = "sent" if sent else ("queued" if not settings.telegram_configured else "failed")
    return _record_alert(
        event_type=event_type,
        title=title,
        message=plain,
        status=status,
        payload=zone.model_dump(mode="json"),
    )


async def send_inference_alert(item: StrategyInference) -> AlertHistoryItem | None:
    if not settings.alerts_enabled:
        return None
    if item.confidence < settings.alert_min_confidence:
        return None

    title = f"Strategy update - {item.trader_alias}"
    message = (
        f"<b>{title}</b>\n"
        f"Strategy: {item.strategy} ({item.trading_style})\n"
        f"Risk: {item.risk_profile} | Confidence: {item.confidence:.0f}%\n"
        f"{item.rationale[:220]}"
    )
    plain = message.replace("<b>", "").replace("</b>", "")
    event_type = "strategy_inference"
    if _is_recent_duplicate(event_type, title, plain):
        return None

    sent = await _send_telegram(message)
    status = "sent" if sent else ("queued" if not settings.telegram_configured else "failed")
    return _record_alert(
        event_type=event_type,
        title=title,
        message=plain,
        status=status,
        payload=item.model_dump(mode="json"),
    )


async def process_alert_triggers(
    whale_alerts: list[WhaleAlert] | None = None,
    zones: list[LiquidationZone] | None = None,
    inferences: list[StrategyInference] | None = None,
) -> list[AlertHistoryItem]:
    created: list[AlertHistoryItem] = []

    for alert in whale_alerts or []:
        item = await send_whale_alert(alert)
        if item:
            created.append(item)

    for zone in zones or []:
        item = await send_squeeze_alert(zone)
        if item:
            created.append(item)

    # Only alert top confidence inferences to avoid spam
    top_inferences = sorted(
        inferences or [],
        key=lambda i: i.confidence,
        reverse=True,
    )[:3]
    for inference in top_inferences:
        item = await send_inference_alert(inference)
        if item:
            created.append(item)

    return created
