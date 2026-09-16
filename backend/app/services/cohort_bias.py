"""BL-06: Smart-money cohort vs rest of tracked book, per major coin."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import (
    CohortBiasAsset,
    CohortBiasResponse,
    PositionSide,
    WhalePosition,
)
from app.services.ranking import SMART_MONEY_SIZE, select_smart_money_ranks
from app.services.store import store
from app.services.whale_book import summarize_whale_book


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _long_pct(positions: list[WhalePosition]) -> tuple[float | None, float, float, int]:
    """Return (long_pct, long_usd, short_usd, whale_count) for a position set."""
    long_usd = 0.0
    short_usd = 0.0
    whales: set[str] = set()
    for pos in positions:
        whales.add(pos.trader_address)
        if pos.side == PositionSide.LONG:
            long_usd += pos.size_usd
        else:
            short_usd += pos.size_usd
    total = long_usd + short_usd
    if total <= 0:
        return None, 0.0, 0.0, 0
    return round(long_usd / total * 100.0, 1), round(long_usd, 2), round(short_usd, 2), len(whales)


def _assets_by_volume() -> list[tuple[str, float]]:
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
    return rows


def _default_assets(limit: int = 5) -> list[str]:
    """Prefer HL volume Top-N, fall back to whale-book notional."""
    rows = _assets_by_volume()
    if rows:
        return [a for a, _ in rows[:limit]]

    summary = store.whale_summary or summarize_whale_book(
        store.whale_positions, tracked=len(store.traders)
    )
    by_size = sorted(
        summary.by_asset.values(),
        key=lambda a: a.long_notional_usd + a.short_notional_usd,
        reverse=True,
    )
    return [a.asset for a in by_size[:limit]]


def _thin_assets(*, exclude: list[str], limit: int = 3) -> list[str]:
    """BL-07: coins outside the volume majors where tracked whales still hold size.

    Thin = not in the liquid head of the board, so whale positioning is a bigger
    share of what is actually there. Ranked by tracked notional, not by volume.
    """
    skip = {a.upper() for a in exclude}
    majors = {a.upper() for a, _ in _assets_by_volume()[:5]}
    summary = store.whale_summary or summarize_whale_book(
        store.whale_positions, tracked=len(store.traders)
    )
    candidates = [
        a
        for a in summary.by_asset.values()
        if a.asset.upper() not in skip and a.asset.upper() not in majors
    ]
    candidates.sort(
        key=lambda a: a.long_notional_usd + a.short_notional_usd, reverse=True
    )
    return [a.asset for a in candidates[: max(0, limit)]]


def _asset_context(asset: str, tracked_notional: float) -> tuple[float | None, float | None]:
    """Return (whale_oi_pct, day_volume_usd) for one asset from live ticks."""
    tick = (store.market_ticks or {}).get(asset)
    if not tick:
        return None, None
    try:
        volume = float(tick.get("day_volume_usd") or 0.0) or None
    except (TypeError, ValueError):
        volume = None
    oi_usd = None
    mark = tick.get("mark_price")
    oi = tick.get("open_interest")
    if mark is not None and oi is not None:
        try:
            oi_usd = float(mark) * float(oi)
        except (TypeError, ValueError):
            oi_usd = None
    whale_oi_pct = None
    if oi_usd and oi_usd > 0 and tracked_notional > 0:
        whale_oi_pct = round(min(100.0, tracked_notional / oi_usd * 100.0), 2)
    return whale_oi_pct, volume


def compute_cohort_bias(
    *,
    assets: list[str] | None = None,
    smart_n: int = SMART_MONEY_SIZE,
    limit: int = 5,
    include_thin: bool = False,
) -> CohortBiasResponse:
    """Compare ranking-top smart money long% vs the rest of the tracked book."""
    if not store.rankings:
        from app.services.ranking import run_ranking_pipeline

        run_ranking_pipeline()

    smart_ranks = select_smart_money_ranks(size=max(1, smart_n))
    smart_addrs = {r.address.lower() for r in smart_ranks}

    if assets:
        wanted = [a.upper() for a in assets]
        thin_set: set[str] = set()
    else:
        majors = _default_assets(limit=limit)
        wanted = [a.upper() for a in majors]
        thin_set = set()
        if include_thin:
            thin = _thin_assets(exclude=wanted, limit=3)
            thin_set = {a.upper() for a in thin}
            wanted = wanted + [a.upper() for a in thin]

    rows: list[CohortBiasAsset] = []
    for asset in wanted:
        smart_pos = [
            p
            for p in store.whale_positions
            if p.asset.upper() == asset and p.trader_address.lower() in smart_addrs
        ]
        rest_pos = [
            p
            for p in store.whale_positions
            if p.asset.upper() == asset and p.trader_address.lower() not in smart_addrs
        ]
        smart_pct, smart_long, smart_short, smart_whales = _long_pct(smart_pos)
        rest_pct, rest_long, rest_short, rest_whales = _long_pct(rest_pos)
        if smart_pct is None and rest_pct is None:
            continue
        delta = None
        if smart_pct is not None and rest_pct is not None:
            delta = round(smart_pct - rest_pct, 1)
        all_pct, _, _, _ = _long_pct(smart_pos + rest_pos)
        tracked_notional = smart_long + smart_short + rest_long + rest_short
        whale_oi_pct, volume = _asset_context(asset, tracked_notional)
        rows.append(
            CohortBiasAsset(
                asset=asset,
                smart_long_pct=smart_pct,
                rest_long_pct=rest_pct,
                delta_pp=delta,
                smart_notional_usd=round(smart_long + smart_short, 2),
                rest_notional_usd=round(rest_long + rest_short, 2),
                smart_whales=smart_whales,
                rest_whales=rest_whales,
                all_long_pct=all_pct,
                whale_oi_pct=whale_oi_pct,
                day_volume_usd=volume,
                thin=asset in thin_set,
            )
        )

    return CohortBiasResponse(
        assets=rows,
        smart_n=len(smart_addrs),
        updated_at=_utcnow(),
    )
