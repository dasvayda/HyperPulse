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
from app.services.brief_schedule import due_market_brief_slot
from app.services.brief_telegram import brief_send_key, format_market_brief_telegram
from app.services.fresh_entries import is_fresh_entry
from app.services.store import store
from app.services.telegram_log import append_telegram_log

logger = logging.getLogger(__name__)

# One-shot "big trade" floor (above normal whale-alert min).
BIG_TRADE_MIN_USD = 2_000_000.0
# Account value heuristic for "known big whale" framing.
BIG_WHALE_ACCOUNT_MIN_USD = 5_000_000.0


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
    cutoff = _utcnow() - timedelta(seconds=max_age_seconds)
    for existing in store.alerts:
        created_at = existing.created_at
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        try:
            if created_at < cutoff:
                break
        except TypeError:
            continue
        if (
            existing.event_type == event_type
            and existing.title == title
            and existing.message == message
            and existing.status in {"sent", "queued"}
        ):
            return True
    return False


def _is_rate_limited(max_per_hour: int) -> bool:
    """Global hourly cap across every Telegram alert."""
    if max_per_hour <= 0:
        return False
    return _count_recent_alerts() >= max_per_hour


def _count_recent_alerts(
    *,
    event_prefixes: tuple[str, ...] | None = None,
    window: timedelta = timedelta(hours=1),
) -> int:
    cutoff = _utcnow() - window
    recent = 0
    for existing in store.alerts:
        created_at = existing.created_at
        if isinstance(created_at, datetime) and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        try:
            if created_at < cutoff:
                break
        except TypeError:
            continue
        if existing.status not in {"sent", "queued"}:
            continue
        if event_prefixes is not None and not any(
            existing.event_type == p or existing.event_type.startswith(p)
            for p in event_prefixes
        ):
            continue
        recent += 1
    return recent


def _limit_key_for_event(event_type: str) -> str:
    if event_type.startswith("big_trade"):
        return "big_trade"
    if event_type.startswith("whale_move"):
        return "whale_move"
    if event_type == "market_consensus":
        return "consensus"
    if event_type == "market_brief":
        return "market_brief"
    if event_type == "squeeze_risk":
        return "squeeze"
    if event_type == "strategy_inference":
        return "style"
    return "other"


def _type_limit(limit_key: str) -> int:
    mapping = {
        "big_trade": settings.alert_limit_big_trade_per_hour,
        "whale_move": settings.alert_limit_whale_move_per_hour,
        "consensus": settings.alert_limit_consensus_per_hour,
        "market_brief": settings.alert_limit_market_brief_per_hour,
        "squeeze": settings.alert_limit_squeeze_per_hour,
        "style": settings.alert_limit_style_per_hour,
    }
    return mapping.get(limit_key, settings.alert_max_per_hour)


def _type_prefixes(limit_key: str) -> tuple[str, ...]:
    mapping = {
        "big_trade": ("big_trade",),
        "whale_move": ("whale_move",),
        "consensus": ("market_consensus",),
        "market_brief": ("market_brief",),
        "squeeze": ("squeeze_risk",),
        "style": ("strategy_inference",),
    }
    return mapping.get(limit_key, (limit_key,))


def _is_type_rate_limited(event_type: str) -> bool:
    """Tighter caps on noisier streams (big_trade > whale_move > consensus)."""
    key = _limit_key_for_event(event_type)
    limit = _type_limit(key)
    if limit <= 0:
        return True
    return _count_recent_alerts(event_prefixes=_type_prefixes(key)) >= limit


def _format_usd_short(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1_000_000_000:
        return f"${abs_v / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"${abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"${abs_v / 1_000:.0f}K"
    return f"${abs_v:.0f}"


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_price(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.4f}"


def _short_addr(address: str) -> str:
    if len(address) < 12:
        return address
    return f"{address[:6]}…{address[-4:]}"


def _trader_for(alert: WhaleAlert):
    needle = alert.trader_address.lower()
    for t in store.traders:
        if t.address.lower() == needle:
            return t
    return None


def _is_known_big_whale(alert: WhaleAlert) -> bool:
    """Large tracked account / smart-money style whale (not just size)."""
    trader = _trader_for(alert)
    if trader and trader.account_value_usd >= BIG_WHALE_ACCOUNT_MIN_USD:
        return True
    try:
        from app.services.ranking import select_smart_money_ranks

        smart = {r.address.lower() for r in select_smart_money_ranks()}
        if alert.trader_address.lower() in smart:
            return True
    except Exception:
        pass
    return False


def classify_position_alert(alert: WhaleAlert) -> str | None:
    """Split position events into whale-move vs one-shot big trade.

    Returns: 'big_whale_move' | 'big_trade' | None (skip).
    """
    if alert.size_usd < settings.alert_min_size_usd:
        return None
    if _alert_is_stale(alert, max_age_minutes=90):
        return None
    if _is_known_big_whale(alert):
        return "big_whale_move"
    if alert.size_usd >= BIG_TRADE_MIN_USD:
        return "big_trade"
    # Mid-size tracked move without big-whale identity → still a trade pulse.
    if alert.size_usd >= settings.alert_min_size_usd * 2:
        return "big_trade"
    return None


def _enrich_alert_for_send(alert: WhaleAlert) -> WhaleAlert:
    from app.collectors.whales import _latest_mark_price
    from app.services.store import _position_roi

    updates: dict = {}
    mark = alert.mark_price
    if mark is None:
        mark = _latest_mark_price(alert.asset)
        if mark is not None:
            updates["mark_price"] = mark
    if (
        alert.entry_price
        and mark is not None
        and (alert.roi_pct is None or alert.unrealized_pnl_usd is None)
    ):
        roi_pct, upnl = _position_roi(
            side=alert.side,
            entry_price=alert.entry_price,
            mark_price=mark,
            size_usd=alert.size_usd,
            leverage=alert.leverage,
        )
        if alert.roi_pct is None and roi_pct is not None:
            updates["roi_pct"] = roi_pct
        if alert.unrealized_pnl_usd is None and upnl is not None:
            updates["unrealized_pnl_usd"] = upnl
    if alert.whale_long_pct is None and store.whale_summary:
        asset_summary = store.whale_summary.by_asset.get(alert.asset)
        if asset_summary:
            updates["whale_long_pct"] = asset_summary.long_pct
    return alert.model_copy(update=updates) if updates else alert


def _alert_is_stale(alert: WhaleAlert, max_age_minutes: int = 45) -> bool:
    ts = alert.timestamp
    if isinstance(ts, datetime) and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    try:
        return (_utcnow() - ts) > timedelta(minutes=max_age_minutes)
    except TypeError:
        return False


CONSENSUS_TOP_N = 3


def _top_assets_by_volume(n: int = CONSENSUS_TOP_N) -> list[str]:
    """Top-N coins by HL 24h notional volume (usually BTC/ETH/SOL)."""
    ticks = store.market_ticks or {}
    rows: list[tuple[str, float]] = []
    for asset, tick in ticks.items():
        try:
            vol = float(tick.get("day_volume_usd") or 0.0)
        except (TypeError, ValueError):
            continue
        if vol > 0:
            rows.append((str(asset), vol))
    rows.sort(key=lambda item: item[1], reverse=True)
    return [asset for asset, _ in rows[:n]]


def _asset_whale_share_line(asset: str, long_pct: float) -> str:
    """Retail-friendly: this coin's tracked-whale long/short $ share."""
    short_pct = max(0.0, 100.0 - long_pct)
    if long_pct >= 55:
        return f"Tracked {asset} whales: {long_pct:.0f}% long / {short_pct:.0f}% short"
    if long_pct <= 45:
        return f"Tracked {asset} whales: {short_pct:.0f}% short / {long_pct:.0f}% long"
    return f"Tracked {asset} whales: mixed ({long_pct:.0f}% long / {short_pct:.0f}% short)"


def _whale_book_share_line(long_pct: float, net_txt: str) -> str:
    """Lead with the dominant side so FEAR/BEARISH don't open on % long."""
    short_pct = 100.0 - long_pct
    if long_pct >= 55:
        return f"Whales {long_pct:.0f}% long / {short_pct:.0f}% short ({net_txt})"
    if long_pct <= 45:
        return f"Whales {short_pct:.0f}% short / {long_pct:.0f}% long ({net_txt})"
    return (
        f"Whales roughly balanced "
        f"({long_pct:.0f}% long / {short_pct:.0f}% short, {net_txt})"
    )


def compute_market_consensus() -> tuple[str, str, float] | None:
    """Return (mood_label, reason_line, long_pct) or None if no book.

    Simplest market-mood read: whale long/short share inside the top-3
    coins by HL 24h volume (usually BTC/ETH/SOL). Funding is intentionally
    excluded here — extreme funding is its own callout (BL-11).
    Moods: EXTREME BULLISH | BULLISH | NEUTRAL | BEARISH | EXTREME BEARISH
    """
    summary = store.whale_summary
    if not summary or summary.with_positions <= 0:
        return None

    top_assets = _top_assets_by_volume()
    long_usd = 0.0
    short_usd = 0.0
    used: list[str] = []
    for asset in top_assets:
        asset_summary = summary.by_asset.get(asset)
        if not asset_summary:
            continue
        long_usd += asset_summary.long_notional_usd
        short_usd += asset_summary.short_notional_usd
        used.append(asset)

    if used and (long_usd + short_usd) > 0:
        scope = f"Top3 by volume ({'/'.join(used)})"
        long_pct = long_usd / (long_usd + short_usd) * 100.0
        net = long_usd - short_usd
    else:
        # No live volume data yet — fall back to the whole tracked book.
        scope = "Whole whale book"
        long_pct = float(summary.long_pct)
        net = summary.net_notional_usd

    net_txt = f"{'+' if net >= 0 else '-'}{_format_usd_short(abs(net))} net"
    book = _whale_book_share_line(long_pct, net_txt)

    if long_pct >= 72:
        mood = "EXTREME BULLISH"
    elif long_pct >= 58:
        mood = "BULLISH"
    elif long_pct <= 28:
        mood = "EXTREME BEARISH"
    elif long_pct <= 42:
        mood = "BEARISH"
    else:
        mood = "NEUTRAL"

    reason = f"{scope}: {book}"
    return mood, reason, long_pct


async def _dispatch(event_type: str, title: str, lines: list[str], payload: dict | None) -> AlertHistoryItem | None:
    if not settings.alerts_enabled:
        return None
    if _is_rate_limited(settings.alert_max_per_hour):
        return None
    if _is_type_rate_limited(event_type):
        return None
    message = "\n".join(lines)
    plain = message.replace("<b>", "").replace("</b>", "")
    if _is_recent_duplicate(event_type, title, plain):
        return None
    sent = await _send_telegram(message)
    status = "sent" if sent else ("queued" if not settings.telegram_configured else "failed")
    append_telegram_log(
        event_type=event_type,
        title=title,
        message_html=message,
        message_plain=plain,
        status=status,
    )
    return _record_alert(event_type, title, plain, status, payload)


async def send_market_brief_alert() -> AlertHistoryItem | None:
    """Desk Market Brief → Telegram, twice a day (Asia 09:00 + US 09:00).

    Insights on the website stay live. Telegram only fires inside a 90-minute
    window after each slot, once per slot. Reuses the Brief already built in
    the inference cycle (no extra LLM call here).
    """
    brief = getattr(store, "market_brief", None)
    if brief is None or (brief.digest is None and brief.tldr is None):
        return None

    slot = due_market_brief_slot(
        last_slot_id=getattr(store, "last_brief_telegram_slot", None),
        brief=brief,
    )
    if slot is None:
        return None

    send_key = brief_send_key(brief)
    title, lines = format_market_brief_telegram(brief)
    if lines:
        lines.insert(1, f"Desk · {slot.label}")
    item = await _dispatch(
        "market_brief",
        title,
        lines,
        {
            "snapshot_hash": send_key,
            "slot_id": slot.slot_id,
            "slot_label": slot.label,
            "stance": brief.stance.value if hasattr(brief.stance, "value") else str(brief.stance),
            "source": brief.source,
            "provider": brief.provider,
            "asset": brief.asset,
        },
    )
    if item and item.status in {"sent", "queued"}:
        store.last_brief_telegram_slot = slot.slot_id
        if send_key:
            store.last_brief_telegram_hash = send_key
    return item


async def send_market_consensus_alert() -> AlertHistoryItem | None:
    """Market-wide mood pulse — fires only when the mood label changes."""
    computed = compute_market_consensus()
    if not computed:
        return None
    mood, reason, long_pct = computed
    if mood == "NEUTRAL":
        return None

    # Same mood as the last sent pulse carries no new information.
    if getattr(store, "last_consensus_label", None) == mood:
        return None
    now = _utcnow()

    title = f"CONSENSUS · {mood}"
    lines = [
        f"<b>{title}</b>",
        reason,
        f"Coverage: {store.whale_summary.with_positions}/{store.whale_summary.tracked} whales positioned",
    ]
    item = await _dispatch(
        "market_consensus",
        title,
        lines,
        {"mood": mood, "long_pct": long_pct, "reason": reason},
    )
    if item and item.status in {"sent", "queued"}:
        store.last_consensus_label = mood
        store.last_consensus_at = now
    return item


def _whale_size_context_lines(alert: WhaleAlert) -> list[str]:
    """Wallet size rank vs Smart Money score rank — two different ladders.

    Size = account value among every tracked whale (1st = biggest wallet).
    Smart Money = score among the 15 largest wallets, not a size rank.
    A whale can be 8th largest and still 14th on the Smart Money board.
    """
    trader = _trader_for(alert)
    lines: list[str] = []

    if trader and trader.account_value_usd > 0:
        size_bits = [f"Wallet {_format_usd_short(trader.account_value_usd)}"]
        by_size = sorted(
            (t for t in store.traders if t.account_value_usd > 0),
            key=lambda t: t.account_value_usd,
            reverse=True,
        )
        for idx, row in enumerate(by_size, start=1):
            if row.address.lower() == alert.trader_address.lower():
                size_bits.append(
                    f"{_ordinal(idx)} largest of {len(by_size)} tracked"
                )
                break
        lines.append(" · ".join(size_bits))
    elif alert.size_usd > 0:
        lines.append(f"Position {_format_usd_short(alert.size_usd)}")

    try:
        from app.services.ranking import SMART_MONEY_SIZE, select_smart_money_ranks

        for row in select_smart_money_ranks():
            if row.address.lower() == alert.trader_address.lower():
                lines.append(
                    "Smart Money score: "
                    f"{_ordinal(row.rank)} of {SMART_MONEY_SIZE} large wallets"
                )
                break
    except Exception:
        pass

    return lines


def format_whale_move_lines(alert: WhaleAlert) -> tuple[str, list[str]]:
    """Title + HTML body lines for a whale-move Telegram."""
    action = "ENTRY" if alert.alert_type.value == "entry" else "EXIT"
    side = alert.side.value.upper()
    fresh = is_fresh_entry(alert)
    title = (
        f"WHALE MOVE · FRESH {action} {alert.asset}"
        if fresh and action == "ENTRY"
        else f"WHALE MOVE · {action} {alert.asset}"
    )

    px = _format_price(
        alert.entry_price
        if alert.alert_type.value == "entry"
        else (alert.exit_price or alert.entry_price)
    )
    verb = "entered" if action == "ENTRY" else "exited"
    line2 = (
        f"{alert.trader_alias} {verb} {side} "
        f"{_format_usd_short(alert.size_usd)} @ {alert.leverage:.0f}x"
    )
    if px:
        px_label = "entry" if action == "ENTRY" else "exit"
        line2 = f"{line2} · {px_label} {px}"
    if alert.size_delta_usd and alert.size_delta_usd > 0 and action == "ENTRY":
        line2 = f"{line2} · added {_format_usd_short(alert.size_delta_usd)}"

    bits: list[str] = []
    if alert.whale_long_pct is not None:
        bits.append(_asset_whale_share_line(alert.asset, alert.whale_long_pct))
    if alert.roi_pct is not None:
        bits.append(f"this pos ROI {alert.roi_pct:+.1f}%")
    elif alert.unrealized_pnl_usd is not None:
        sign = "+" if alert.unrealized_pnl_usd >= 0 else "-"
        bits.append(f"this pos uPnL {sign}{_format_usd_short(abs(alert.unrealized_pnl_usd))}")

    lines = [f"<b>{title}</b>", line2]
    lines.extend(_whale_size_context_lines(alert))
    if bits:
        lines.append(" · ".join(bits))
    lines.append(_short_addr(alert.trader_address))
    return title, lines


async def send_big_whale_move(alert: WhaleAlert) -> AlertHistoryItem | None:
    """Known large account position move — short and directional."""
    if alert.confidence_score < settings.alert_min_confidence:
        return None
    alert = _enrich_alert_for_send(alert)
    title, lines = format_whale_move_lines(alert)
    return await _dispatch(
        f"whale_move_{alert.alert_type.value}",
        title,
        lines,
        alert.model_dump(mode="json"),
    )


async def send_big_trade(alert: WhaleAlert) -> AlertHistoryItem | None:
    """Large one-shot notional bet — size-first, identity secondary.

    Inspired by whale-alerts.net: category + size matter; keep it punchy.
    """
    alert = _enrich_alert_for_send(alert)
    side = alert.side.value.upper()
    action = "IN" if alert.alert_type.value == "entry" else "OUT"
    fresh = is_fresh_entry(alert)
    title = (
        f"BIG TRADE · FRESH {side} {action} {alert.asset}"
        if fresh and action == "IN"
        else f"BIG TRADE · {side} {action} {alert.asset}"
    )

    px = _format_price(
        alert.entry_price
        if alert.alert_type.value == "entry"
        else (alert.exit_price or alert.entry_price or alert.mark_price)
    )
    line2 = f"{_format_usd_short(alert.size_usd)} one-shot · {alert.leverage:.0f}x"
    if px:
        line2 = f"{line2} · {px}"

    lines = [
        f"<b>{title}</b>",
        line2,
        f"Wallet {_short_addr(alert.trader_address)}",
    ]
    if alert.whale_long_pct is not None:
        lines.append(_asset_whale_share_line(alert.asset, alert.whale_long_pct))

    return await _dispatch(
        f"big_trade_{alert.alert_type.value}",
        title,
        lines,
        alert.model_dump(mode="json"),
    )


# Backward-compatible name used by older call sites / tests.
async def send_whale_alert(alert: WhaleAlert) -> AlertHistoryItem | None:
    kind = classify_position_alert(alert)
    if kind == "big_whale_move":
        return await send_big_whale_move(alert)
    if kind == "big_trade":
        return await send_big_trade(alert)
    return None


async def send_squeeze_alert(zone: LiquidationZone) -> AlertHistoryItem | None:
    if zone.size_usd < 100_000_000:
        return None
    title = f"SQUEEZE · {zone.asset}"
    lines = [
        f"<b>{title}</b>",
        f"{zone.side.value.upper()} liq cluster {_format_usd_short(zone.size_usd)} @ {_format_price(zone.price) or zone.price}",
        f"Distance {zone.distance_pct:+.1f}% · OI share {zone.open_interest_pct:.1f}%",
    ]
    return await _dispatch("squeeze_risk", title, lines, zone.model_dump(mode="json"))


async def send_inference_alert(item: StrategyInference) -> AlertHistoryItem | None:
    """Deprecated for default Telegram mix — kept for manual/API use."""
    if item.confidence < settings.alert_min_confidence:
        return None
    title = f"STYLE · {item.trader_alias}"
    lines = [
        f"<b>{title}</b>",
        f"{item.strategy} · {item.trading_style}",
        f"Risk {item.risk_profile} · {item.confidence:.0f}%",
    ]
    return await _dispatch(
        "strategy_inference",
        title,
        lines,
        item.model_dump(mode="json"),
    )


async def process_alert_triggers(
    whale_alerts: list[WhaleAlert] | None = None,
    zones: list[LiquidationZone] | None = None,
    inferences: list[StrategyInference] | None = None,
) -> list[AlertHistoryItem]:
    """Mix alert types so Telegram is not a wall of similar whale lines.

    Per-type hourly caps (see config) — big_trade is tightest because it fires most.
    Per cycle: at most alert_*_per_cycle of each position type.
    Market Brief Telegram fires at Asia 09:00 and US 09:00 (90-minute window, once per slot).
    Strategy-inference spam is intentionally skipped in the default mix.
    """
    created: list[AlertHistoryItem] = []
    _ = inferences  # reserved; not mixed into Telegram by default

    brief_item = await send_market_brief_alert()
    if brief_item:
        created.append(brief_item)

    item = await send_market_consensus_alert()
    if item:
        created.append(item)

    candidates = list(whale_alerts or store.whale_alerts[:30])
    moves: list[WhaleAlert] = []
    trades: list[WhaleAlert] = []
    for alert in candidates:
        kind = classify_position_alert(alert)
        if kind == "big_whale_move":
            moves.append(alert)
        elif kind == "big_trade":
            trades.append(alert)

    moves.sort(key=lambda a: a.size_usd, reverse=True)
    trades.sort(key=lambda a: a.size_usd, reverse=True)

    move_budget = max(0, settings.alert_whale_move_per_cycle)
    for alert in moves:
        if move_budget <= 0:
            break
        if _is_rate_limited(settings.alert_max_per_hour) or _is_type_rate_limited(
            "whale_move_entry"
        ):
            break
        item = await send_big_whale_move(alert)
        if item:
            created.append(item)
            move_budget -= 1

    trade_budget = max(0, settings.alert_big_trade_per_cycle)
    move_ids = {m.id for m in moves[: settings.alert_whale_move_per_cycle]}
    for alert in trades:
        if trade_budget <= 0:
            break
        if alert.id in move_ids:
            continue
        if _is_rate_limited(settings.alert_max_per_hour) or _is_type_rate_limited(
            "big_trade_entry"
        ):
            break
        item = await send_big_trade(alert)
        if item:
            created.append(item)
            trade_budget -= 1

    if zones and not (
        _is_rate_limited(settings.alert_max_per_hour)
        or _is_type_rate_limited("squeeze_risk")
    ):
        for zone in zones[:1]:
            item = await send_squeeze_alert(zone)
            if item:
                created.append(item)
                break

    return created
