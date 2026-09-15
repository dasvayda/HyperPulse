"""BL-10: market-wide OI / Vol / Liq pulse with short deltas."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.orm import MarketSnapshotRow
from app.models.schemas import MarketPulse
from app.services.liq_windows import rollup_liq_windows
from app.services.store import store


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tick_oi_usd(tick: dict) -> float:
    mark = tick.get("mark_price")
    oi = tick.get("open_interest")
    if mark is None or oi is None:
        return 0.0
    try:
        return float(mark) * float(oi)
    except (TypeError, ValueError):
        return 0.0


def _aggregate_live(*, top_n: int = 20) -> tuple[float, float, list[str]]:
    ticks = list((store.market_ticks or {}).values())
    ticks.sort(key=lambda t: float(t.get("day_volume_usd") or 0.0), reverse=True)
    picked = ticks[:top_n]
    oi = sum(_tick_oi_usd(t) for t in picked)
    vol = 0.0
    assets: list[str] = []
    for t in picked:
        try:
            vol += float(t.get("day_volume_usd") or 0.0)
        except (TypeError, ValueError):
            pass
        assets.append(str(t.get("asset") or ""))
    return round(oi, 2), round(vol, 2), [a for a in assets if a]


def _prior_snapshot_totals(
    db: Session,
    *,
    assets: list[str],
    hours_ago: float = 1.0,
) -> tuple[float | None, float | None]:
    """Sum OI·mark and day volume for the same assets near T−hours_ago."""
    if not assets:
        return None, None
    now = _utcnow()
    target = now - timedelta(hours=hours_ago)
    window_start = target - timedelta(minutes=45)
    window_end = target + timedelta(minutes=45)

    oi_total = 0.0
    vol_total = 0.0
    found = 0
    for asset in assets:
        row = (
            db.query(MarketSnapshotRow)
            .filter(
                MarketSnapshotRow.asset == asset,
                MarketSnapshotRow.timestamp >= window_start,
                MarketSnapshotRow.timestamp <= window_end,
            )
            .order_by(MarketSnapshotRow.timestamp.desc())
            .first()
        )
        if row is None:
            continue
        found += 1
        oi_total += float(row.mark_price) * float(row.open_interest or 0.0)
        vol_total += float(getattr(row, "day_volume_usd", 0.0) or 0.0)
    if found == 0:
        return None, None
    return round(oi_total, 2), round(vol_total, 2)


def _delta_pct(current: float, prior: float | None) -> float | None:
    if prior is None or prior <= 0:
        return None
    return round((current - prior) / prior * 100.0, 2)


def compute_market_pulse(*, top_n: int = 20) -> MarketPulse:
    oi_usd, vol_usd, assets = _aggregate_live(top_n=top_n)
    windows = rollup_liq_windows(_utcnow())
    w24 = windows.get("24h") or {}
    liq_usd = float(w24.get("total_usd") or 0.0)
    w1 = windows.get("1h") or {}
    # Approximate short Δ for liq: 1h total vs (24h/24) baseline rate.
    baseline_1h = liq_usd / 24.0 if liq_usd > 0 else 0.0
    liq_1h = float(w1.get("total_usd") or 0.0)
    liq_delta = _delta_pct(liq_1h, baseline_1h) if baseline_1h > 0 else None

    oi_delta = None
    vol_delta = None
    db: Session = SessionLocal()
    try:
        prior_oi, prior_vol = _prior_snapshot_totals(db, assets=assets, hours_ago=1.0)
        oi_delta = _delta_pct(oi_usd, prior_oi)
        vol_delta = _delta_pct(vol_usd, prior_vol)
    finally:
        db.close()

    return MarketPulse(
        oi_usd=oi_usd,
        oi_delta_pct=oi_delta,
        vol_usd_24h=vol_usd,
        vol_delta_pct=vol_delta,
        liq_usd_24h=round(liq_usd, 2),
        liq_delta_pct=liq_delta,
        scope=f"top{top_n}",
        as_of=_utcnow(),
    )
