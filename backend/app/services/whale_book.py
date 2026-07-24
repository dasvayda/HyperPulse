from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.models.schemas import (
    AssetWhaleSummary,
    BiggestPosition,
    PositionSide,
    WhaleBookSummary,
    WhalePosition,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _net_bias(long_usd: float, short_usd: float) -> str:
    if long_usd > short_usd * 1.1:
        return "long"
    if short_usd > long_usd * 1.1:
        return "short"
    return "neutral"


def index_positions_by_trader(
    positions: list[WhalePosition],
) -> dict[str, list[WhalePosition]]:
    by_trader: dict[str, list[WhalePosition]] = defaultdict(list)
    for pos in positions:
        by_trader[pos.trader_address].append(pos)
    return dict(by_trader)


def summarize_whale_book(
    positions: list[WhalePosition],
    tracked: int,
    updated_at: datetime | None = None,
) -> WhaleBookSummary:
    updated_at = updated_at or _utcnow()
    long_total = 0.0
    short_total = 0.0
    net_by_trader: dict[str, float] = defaultdict(float)
    by_asset: dict[str, dict] = defaultdict(
        lambda: {
            "long": 0.0,
            "short": 0.0,
            "whales": set(),
            "lev_total": 0.0,
            "count": 0,
        }
    )

    for pos in positions:
        bucket = by_asset[pos.asset]
        bucket["whales"].add(pos.trader_address)
        bucket["lev_total"] += pos.leverage
        bucket["count"] += 1
        signed = pos.size_usd if pos.side.value == "long" else -pos.size_usd
        net_by_trader[pos.trader_address] += signed
        if pos.side.value == "long":
            long_total += pos.size_usd
            bucket["long"] += pos.size_usd
        else:
            short_total += pos.size_usd
            bucket["short"] += pos.size_usd

    total = long_total + short_total
    long_pct = round(long_total / total * 100.0, 1) if total > 0 else 0.0
    net_notional = long_total - short_total

    # Classify each whale by its net exposure across all assets, so the "simple
    # count" view answers "how many whales are net long vs net short" rather
    # than counting individual positions (a whale can hold several).
    long_whale_count = sum(1 for net in net_by_trader.values() if net > 0)
    short_whale_count = sum(1 for net in net_by_trader.values() if net < 0)
    neutral_whale_count = sum(1 for net in net_by_trader.values() if net == 0)
    whale_count_total = long_whale_count + short_whale_count
    whale_count_long_pct = (
        round(long_whale_count / whale_count_total * 100.0, 1) if whale_count_total > 0 else 0.0
    )

    assets: dict[str, AssetWhaleSummary] = {}
    for asset, data in by_asset.items():
        asset_total = data["long"] + data["short"]
        asset_long_pct = round(data["long"] / asset_total * 100.0, 1) if asset_total > 0 else 0.0
        avg_lev = round(data["lev_total"] / data["count"], 2) if data["count"] else 0.0
        net_notional_asset = data["long"] - data["short"]
        assets[asset] = AssetWhaleSummary(
            asset=asset,
            whales=len(data["whales"]),
            long_notional_usd=round(data["long"], 2),
            short_notional_usd=round(data["short"], 2),
            long_pct=asset_long_pct,
            net_notional_usd=round(net_notional_asset, 2),
            net_bias=_net_bias(data["long"], data["short"]),
            avg_leverage=avg_lev,
        )

    return WhaleBookSummary(
        tracked=tracked,
        with_positions=len({p.trader_address for p in positions}),
        long_notional_usd=round(long_total, 2),
        short_notional_usd=round(short_total, 2),
        long_pct=long_pct,
        net_notional_usd=round(net_notional, 2),
        net_bias=_net_bias(long_total, short_total),
        long_whale_count=long_whale_count,
        short_whale_count=short_whale_count,
        neutral_whale_count=neutral_whale_count,
        whale_count_long_pct=whale_count_long_pct,
        updated_at=updated_at,
        by_asset=assets,
    )


def whale_bias_label(long_pct: float | None) -> str | None:
    """Tracked-whale long share — retail-friendly long/short wording."""
    if long_pct is None:
        return None
    if long_pct >= 70:
        return "Long heavy"
    if long_pct >= 58:
        return "Mostly long"
    if long_pct <= 30:
        return "Short heavy"
    if long_pct <= 42:
        return "Mostly short"
    return "Mixed"


def asset_market_tag(asset: str) -> str | None:
    """Cheap tag for non-crypto / HIP-style names without a full meta parse."""
    upper = asset.upper()
    if upper.startswith("XYZ"):
        return "xyz"
    # Common HIP-3 / tradfi-style symbols seen on Hyperliquid boards.
    tradfi = {
        "SP500",
        "SKHX",
        "BRENTOIL",
        "GOLD",
        "SILVER",
        "EUR",
        "JPY",
        "TSLA",
        "NVDA",
        "AAPL",
        "MSFT",
        "AMZN",
        "META",
        "GOOGL",
        "COIN",
        "MSTR",
        "HOOD",
        "PLTR",
        "CRCL",
        "XYZ100",
    }
    if upper in tradfi:
        return "xyz"
    return None


def list_biggest_positions(
    positions: list[WhalePosition],
    *,
    traders_by_addr: dict[str, str],
    marks: dict[str, float] | None = None,
    limit: int = 8,
) -> list[BiggestPosition]:
    """Tracked-universe biggest open positions by notional (BL-04)."""
    from app.services.store import _position_roi

    marks = marks or {}
    ranked = sorted(positions, key=lambda p: p.size_usd, reverse=True)[: max(1, limit)]
    out: list[BiggestPosition] = []
    for idx, pos in enumerate(ranked, start=1):
        mark = marks.get(pos.asset)
        roi_pct = None
        upnl = None
        if mark and mark > 0:
            roi_pct, upnl = _position_roi(
                side=pos.side,
                entry_price=pos.entry_price,
                mark_price=mark,
                size_usd=pos.size_usd,
                leverage=pos.leverage,
            )
        alias = traders_by_addr.get(pos.trader_address) or (
            f"{pos.trader_address[:6]}...{pos.trader_address[-4:]}"
            if len(pos.trader_address) > 12
            else pos.trader_address
        )
        out.append(
            BiggestPosition(
                rank=idx,
                trader_address=pos.trader_address,
                trader_alias=alias,
                asset=pos.asset,
                side=pos.side,
                size_usd=round(pos.size_usd, 2),
                entry_price=pos.entry_price,
                leverage=pos.leverage,
                mark_price=mark,
                roi_pct=roi_pct,
                unrealized_pnl_usd=upnl,
            )
        )
    return out
