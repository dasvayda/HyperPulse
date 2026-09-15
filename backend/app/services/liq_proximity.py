"""BL-12: tracked-whale distance to liquidation."""

from __future__ import annotations

from app.models.schemas import (
    LiqProximityRow,
    PositionSide,
    WhalePosition,
)
from app.services.store import store


def liq_distance_pct(
    *,
    side: PositionSide | str,
    mark: float,
    liquidation_px: float,
) -> float | None:
    """How far mark is from liq, as % of mark. Lower = closer danger.

    Long: ((mark - liq) / mark) * 100
    Short: ((liq - mark) / mark) * 100
    Negative means mark already past the liq price.
    """
    if mark <= 0 or liquidation_px <= 0:
        return None
    side_val = side.value if isinstance(side, PositionSide) else str(side).lower()
    if side_val == "long":
        return round((mark - liquidation_px) / mark * 100.0, 2)
    if side_val == "short":
        return round((liquidation_px - mark) / mark * 100.0, 2)
    return None


def estimate_liquidation_px(
    *,
    side: PositionSide | str,
    entry_price: float,
    leverage: float,
) -> float | None:
    """Rough fallback when HL liquidationPx is missing (maintains ~10% buffer of 1/lev)."""
    if entry_price <= 0 or leverage <= 0:
        return None
    # Use 90% of inverse leverage as a conservative maintenance proxy.
    move = 0.9 / leverage
    side_val = side.value if isinstance(side, PositionSide) else str(side).lower()
    if side_val == "long":
        px = entry_price * (1.0 - move)
        return round(px, 6) if px > 0 else None
    if side_val == "short":
        return round(entry_price * (1.0 + move), 6)
    return None


def list_liq_proximity(
    positions: list[WhalePosition] | None = None,
    *,
    marks: dict[str, float] | None = None,
    traders_by_addr: dict[str, str] | None = None,
    limit: int = 10,
) -> list[LiqProximityRow]:
    """Closest-to-liq tracked positions (ascending distance%)."""
    positions = positions if positions is not None else store.whale_positions
    if marks is None:
        marks = {}
        for asset, tick in (store.market_ticks or {}).items():
            mark = tick.get("mark_price")
            if mark is not None:
                try:
                    marks[str(asset)] = float(mark)
                except (TypeError, ValueError):
                    pass
    traders_by_addr = traders_by_addr or {t.address: t.alias for t in store.traders}

    scored: list[tuple[float, LiqProximityRow]] = []
    for pos in positions:
        mark = marks.get(pos.asset)
        if mark is None or mark <= 0:
            continue
        source = "liquidationPx"
        liq_px = pos.liquidation_px
        if liq_px is None or liq_px <= 0:
            liq_px = estimate_liquidation_px(
                side=pos.side,
                entry_price=pos.entry_price,
                leverage=pos.leverage,
            )
            source = "estimate"
        if liq_px is None:
            continue
        dist = liq_distance_pct(side=pos.side, mark=mark, liquidation_px=liq_px)
        if dist is None:
            continue
        alias = traders_by_addr.get(pos.trader_address) or (
            f"{pos.trader_address[:6]}...{pos.trader_address[-4:]}"
            if len(pos.trader_address) > 12
            else pos.trader_address
        )
        scored.append(
            (
                dist,
                LiqProximityRow(
                    rank=0,
                    trader_address=pos.trader_address,
                    trader_alias=alias,
                    asset=pos.asset,
                    side=pos.side,
                    size_usd=round(pos.size_usd, 2),
                    leverage=pos.leverage,
                    mark_price=round(mark, 6),
                    liquidation_px=liq_px,
                    distance_pct=dist,
                    source=source,  # type: ignore[arg-type]
                ),
            )
        )

    scored.sort(key=lambda item: item[0])
    out: list[LiqProximityRow] = []
    for idx, (_, row) in enumerate(scored[: max(1, limit)], start=1):
        out.append(row.model_copy(update={"rank": idx}))
    return out
