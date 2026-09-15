"""BL-08: copy-worthiness / due-diligence verdict for a trader."""

from __future__ import annotations

from enum import Enum

from app.models.schemas import CopyVerdict, OpenPosition


class CopyLabel(str, Enum):
    WATCH = "watch"
    CAUTION = "caution"
    SKIP = "skip"


def compute_copy_verdict(
    *,
    smart_money_score: float | None,
    open_roi_pct: float | None,
    open_unrealized_pnl_usd: float | None,
    max_leverage: float | None,
    risk_score: float | None,
    inference_confidence: float | None,
    open_positions: list[OpenPosition] | None = None,
) -> CopyVerdict:
    """Heuristic Watch / Caution / Skip from ranking + open book + inference.

    Rules (documented for reproducibility):
    - Skip if max lev >= 25, or open ROI <= -40%, or risk_score >= 85
    - Watch if score >= 60 and open ROI >= 0 (or no open book) and max lev < 15
      and (inference conf >= 55 or missing)
    - Else Caution
    """
    reasons: list[str] = []
    positions = open_positions or []
    if max_leverage is None and positions:
        max_leverage = max((p.leverage for p in positions), default=None)
    if open_roi_pct is None and positions:
        # Weighted by notional when possible.
        total = sum(p.size_usd for p in positions if p.roi_pct is not None)
        if total > 0:
            open_roi_pct = round(
                sum((p.roi_pct or 0.0) * p.size_usd for p in positions if p.roi_pct is not None)
                / total,
                2,
            )
    if open_unrealized_pnl_usd is None and positions:
        if any(p.unrealized_pnl_usd is not None for p in positions):
            open_unrealized_pnl_usd = round(
                sum(p.unrealized_pnl_usd or 0.0 for p in positions), 2
            )

    score = smart_money_score
    roi = open_roi_pct
    lev = max_leverage
    risk = risk_score if risk_score is not None else 50.0
    conf = inference_confidence

    if lev is not None and lev >= 25:
        reasons.append(f"Max leverage {lev:.0f}x is extreme")
        return CopyVerdict(verdict=CopyLabel.SKIP.value, reasons=reasons[:3])
    if roi is not None and roi <= -40:
        reasons.append(f"Open ROI {roi:+.0f}% is deeply underwater")
        return CopyVerdict(verdict=CopyLabel.SKIP.value, reasons=reasons[:3])
    if risk >= 85:
        reasons.append(f"Risk score {risk:.0f}/100 is very high")
        return CopyVerdict(verdict=CopyLabel.SKIP.value, reasons=reasons[:3])

    watch_ok = True
    if score is not None:
        if score >= 60:
            reasons.append(f"Smart money score {score:.0f}/100")
        else:
            watch_ok = False
            reasons.append(f"Smart money score only {score:.0f}/100")
    else:
        watch_ok = False
        reasons.append("No smart money score yet")

    if roi is not None:
        if roi >= 0:
            reasons.append(f"Open ROI {roi:+.1f}%")
        else:
            watch_ok = False
            reasons.append(f"Open ROI {roi:+.1f}%")
    elif not positions:
        reasons.append("No open positions to stress")

    if lev is not None:
        if lev < 15:
            reasons.append(f"Max lev {lev:.0f}x")
        else:
            watch_ok = False
            reasons.append(f"Max lev {lev:.0f}x is elevated")

    if conf is not None and conf < 55:
        watch_ok = False
        reasons.append(f"Style confidence {conf:.0f}% is low")
    elif conf is not None:
        reasons.append(f"Style confidence {conf:.0f}%")

    if risk >= 70:
        watch_ok = False
        reasons.append(f"Risk score {risk:.0f}/100")

    verdict = CopyLabel.WATCH.value if watch_ok else CopyLabel.CAUTION.value
    return CopyVerdict(verdict=verdict, reasons=reasons[:3])
