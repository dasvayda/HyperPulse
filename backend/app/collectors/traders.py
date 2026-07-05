from __future__ import annotations

import logging
import statistics
from typing import Any

from app.collectors.hyperliquid_client import stats as hl_stats
from app.config import settings
from app.models.schemas import TraderProfile
from app.services.store import store

logger = logging.getLogger(__name__)


def _window_map(row: dict) -> dict[str, dict]:
    windows: dict[str, dict] = {}
    raw = row.get("windowPerformances") or row.get("window_performances") or []
    if not isinstance(raw, list):
        return windows
    for entry in raw:
        if isinstance(entry, list) and len(entry) >= 2 and isinstance(entry[1], dict):
            windows[str(entry[0]).lower()] = entry[1]
        elif isinstance(entry, dict):
            label = entry.get("window") or entry.get("period")
            if isinstance(label, str):
                windows[label.lower()] = entry
    return windows


def _sparkline_from_windows(windows: dict[str, dict]) -> list[float]:
    values: list[float] = []
    for label in ("day", "week", "month", "alltime", "all_time"):
        perf = windows.get(label)
        if not perf:
            continue
        try:
            values.append(float(perf.get("pnl", 0)))
        except Exception:
            continue
    return values


def _risk_from_windows(windows: dict[str, dict]) -> float:
    rois: list[float] = []
    for perf in windows.values():
        try:
            rois.append(float(perf.get("roi", 0)) * 100.0)
        except Exception:
            continue
    if len(rois) < 2:
        return 50.0
    vol = statistics.pstdev(rois)
    return round(max(10.0, min(100.0, 30.0 + vol * 8.0)), 1)


def _extract_all_time(perf: Any) -> dict | None:
    if isinstance(perf, dict):
        # Either {"allTime": {...}} or nested
        if "allTime" in perf:
            return perf.get("allTime")  # type: ignore[return-value]
        if "alltime" in perf:
            return perf.get("alltime")  # type: ignore[return-value]
        return None
    if isinstance(perf, list):
        # [["allTime", {...}], ...]
        for entry in perf:
            if (
                isinstance(entry, list)
                and len(entry) >= 2
                and isinstance(entry[0], str)
                and entry[0].lower() in {"alltime", "all_time"}
                and isinstance(entry[1], dict)
            ):
                return entry[1]
    return None


async def collect_top_traders() -> list[TraderProfile]:
    """Fetch top traders from Hyperliquid stats leaderboard and update store."""
    if settings.use_mock_data:
        # Respect existing seed-based behaviour when mock mode is enabled.
        return store.traders

    try:
        raw = await hl_stats("leaderboard")
    except Exception as exc:
        logger.warning("Failed to fetch leaderboard: %s", exc)
        return store.traders

    # The stats API currently returns a dict with "leaderboardRows" (camelCase).
    if isinstance(raw, dict):
        rows = (
            raw.get("leaderboard_rows")
            or raw.get("leaderboardRows")
            or raw.get("leaderboard")
            or raw.get("rows")
            or []
        )
    else:
        rows = raw

    if not isinstance(rows, list):
        logger.warning("Unexpected leaderboard payload type: %s", type(raw))
        return store.traders

    limit = max(1, settings.tracked_trader_limit)
    traders: list[TraderProfile] = []

    for rank, row in enumerate(rows[:limit], start=1):
        if not isinstance(row, dict):
            continue
        address = (
            row.get("ethAddress")
            or row.get("user")
            or row.get("address")
        )
        if not isinstance(address, str) or not address:
            continue

        display = row.get("displayName") or row.get("display_name")
        if isinstance(display, str) and display:
            alias = display
        else:
            alias = f"{address[:6]}...{address[-4:]}"

        account_value_raw = row.get("accountValue") or row.get("account_value") or "0"
        try:
            account_value = float(account_value_raw)
        except Exception:
            account_value = 0.0

        windows = _window_map(row)
        perf = windows.get("alltime") or windows.get("all_time")
        if perf is None:
            perf = _extract_all_time(row.get("windowPerformances") or row.get("window_performances"))
        pnl_usd = account_value
        pnl_change_pct = 0.0
        volume_usd = 0.0
        sparkline = _sparkline_from_windows(windows)

        if isinstance(perf, dict):
            pnl_raw = perf.get("pnl", "0")
            roi_raw = perf.get("roi", "0")
            vlm_raw = perf.get("vlm", "0")
            history = perf.get("accountValueHistory") or []
            try:
                pnl_usd = float(pnl_raw)
            except Exception:
                pnl_usd = account_value
            try:
                roi = float(roi_raw)
                # ROI is typically in decimal form (0.12 -> 12%)
                pnl_change_pct = roi * 100.0
            except Exception:
                pnl_change_pct = 0.0
            try:
                volume_usd = float(vlm_raw)
            except Exception:
                volume_usd = 0.0
            if isinstance(history, list) and history:
                # history: [[ts, value], ...]
                values: list[float] = []
                for entry in history[-10:]:
                    if isinstance(entry, list) and len(entry) >= 2:
                        try:
                            values.append(float(entry[1]))
                        except Exception:
                            continue
                if values:
                    sparkline = values

        risk_score = _risk_from_windows(windows)

        trader = TraderProfile(
            address=address,
            alias=alias,
            rank=rank,
            pnl_usd=pnl_usd,
            pnl_change_pct=pnl_change_pct,
            account_value_usd=account_value,
            volume_usd=volume_usd,
            win_rate=0.0,
            avg_hold_hours=0.0,
            total_trades=0,
            preferred_assets=[],
            strategy_tags=[],
            risk_score=risk_score,
            sparkline=sparkline or [0.0] * 4,
        )
        traders.append(trader)

    if not traders:
        return store.traders

    with store._lock:
        store.traders = traders
    store.persist_traders(traders)
    store.refresh_dashboard()
    logger.info("Updated traders from leaderboard: %s", len(traders))
    return traders

