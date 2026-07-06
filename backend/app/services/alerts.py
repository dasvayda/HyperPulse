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


def _format_price(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _behavior_label(alert: WhaleAlert) -> tuple[str, str, float, int]:
    positions = store.whale_positions_by_trader.get(alert.trader_address, [])
    if not positions:
        return ("Active", "Balanced", alert.leverage, 0)
    avg_lev = sum(p.leverage for p in positions) / len(positions)
    if avg_lev >= 20:
        label = "High-Lev Speculative"
        risk = "Aggressive"
    elif len(positions) >= 4:
        label = "Diversified"
        risk = "Balanced"
    elif len(positions) == 1:
        label = "Directional"
        risk = "Balanced" if avg_lev >= 8 else "Conservative"
    else:
        label = "Active"
        risk = "Balanced" if avg_lev >= 8 else "Conservative"
    return (label, risk, avg_lev, len(positions))


def _book_context_line(asset: str) -> str | None:
    summary = store.whale_summary
    if not summary:
        return None
    asset_summary = summary.by_asset.get(asset)
    if not asset_summary:
        return None
    net = asset_summary.net_notional_usd
    net_label = f"+${abs(net) / 1_000_000:.1f}M" if net >= 0 else f"-${abs(net) / 1_000_000:.1f}M"
    return f"Book: {asset_summary.long_pct:.0f}% long ({net_label} net)"


async def send_whale_alert(alert: WhaleAlert) -> AlertHistoryItem | None:
    if not settings.alerts_enabled:
        return None
    if alert.confidence_score < settings.alert_min_confidence:
        return None
    if alert.size_usd < settings.alert_min_size_usd:
        return None

    title = f"Whale {alert.alert_type.value.upper()} - {alert.asset}"
    price = alert.entry_price if alert.alert_type.value == "entry" else (alert.exit_price or alert.entry_price)
    price_label = _format_price(price)
    side_line = f"Side: {alert.side.value.upper()} | Size: ${alert.size_usd:,.0f}"
    if price_label:
        side_line = f"{side_line} @ {price_label}"

    behavior_label, risk_label, avg_lev, open_positions = _behavior_label(alert)
    behavior_line = (
        f"Style: {behavior_label} (avg lev {avg_lev:.1f}x, {open_positions} open)"
        if open_positions
        else f"Style: {behavior_label}"
    )

    trader = next((t for t in store.traders if t.address == alert.trader_address), None)
    win_rate_line = None
    if trader and trader.total_trades > 0:
        win_rate_line = f"Win rate: {trader.win_rate:.1f}% ({trader.total_trades} trades)"

    strategy_line = None
    if alert.inferred_strategy and alert.inferred_strategy.lower() != "unknown":
        strategy_line = f"Strategy: {alert.inferred_strategy} ({alert.confidence_score:.0f}% conf)"

    lines = [
        f"<b>{title}</b>",
        f"Trader: {alert.trader_alias} ({alert.trader_address})",
        side_line,
        f"Leverage: {alert.leverage}x | Risk: {risk_label}",
    ]
    if win_rate_line:
        lines.append(win_rate_line)
    lines.append(behavior_line)
    if strategy_line:
        lines.append(strategy_line)
    book_line = _book_context_line(alert.asset)
    if book_line:
        lines.append(book_line)
    message = "\n".join(lines)
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
