"""Rule-based Market Brief TL;DR, tape, and coin slicing (no LLM)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.schemas import BriefTldr

BOOK_LONG_HEAVY = 58.0
BOOK_SHORT_HEAVY = 42.0
TENSION_MIN_ABS_PCT = 1.0
STALE_AFTER = timedelta(minutes=45)
LIQ_QUIET_USD = 250_000.0
LIQ_SKEW_RATIO = 1.5
LIQ_24H_SKEW_USD = 1_000_000.0

_PREFER_TAIL_RE = re.compile(
    r"(?:\s*[—\-]\s*)?(?:prefer\s+longs?|prefer\s+shorts?|\bwait\b)\s*$",
    re.I,
)
_PREFER_HEADLINE_RE = re.compile(r"\bprefer\s+(longs?|shorts?)\b", re.I)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw
    if not raw:
        return None
    text = str(raw).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_usd_short(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1_000_000_000:
        return f"${abs_v / 1_000_000_000:.1f}B"
    if abs_v >= 1_000_000:
        return f"${abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"${abs_v / 1_000:.1f}K"
    return f"${abs_v:.0f}"


def format_mark(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.4f}"


def tab_assets(snapshot: dict[str, Any]) -> list[str]:
    consensus = snapshot.get("top3_consensus") or {}
    assets = [str(a).upper() for a in (consensus.get("assets") or []) if a]
    if assets:
        return assets[:3]
    tape = snapshot.get("tape") or {}
    ranked = sorted(
        tape.values(),
        key=lambda row: float(row.get("day_volume_usd") or 0.0),
        reverse=True,
    )
    return [str(row["asset"]).upper() for row in ranked[:3] if row.get("asset")]


def coverage_label(snapshot: dict[str, Any]) -> str:
    cov = snapshot.get("coverage") or {}
    return f"{int(cov.get('positioned') or 0)}/{int(cov.get('tracked') or 0)}"


def snapshot_stale(snapshot: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or _utcnow()
    stamps: list[datetime] = []
    for key in ("book_updated_at", "tape_updated_at"):
        parsed = _parse_dt(snapshot.get(key))
        if parsed:
            stamps.append(parsed)
    tape = snapshot.get("tape") or {}
    for row in tape.values():
        parsed = _parse_dt(row.get("updated_at"))
        if parsed:
            stamps.append(parsed)
    if not stamps:
        return False
    newest = max(stamps)
    return (now - newest) >= STALE_AFTER


def price_vs_book_tension(
    change_pct_24h: float | None,
    long_pct: float | None,
) -> str | None:
    if change_pct_24h is None or long_pct is None:
        return None
    if abs(change_pct_24h) < TENSION_MIN_ABS_PCT:
        return None
    if BOOK_SHORT_HEAVY < long_pct < BOOK_LONG_HEAVY:
        return None
    if change_pct_24h < 0 and long_pct >= BOOK_LONG_HEAVY:
        return (
            f"price vs prev day {change_pct_24h:+.1f}% while tracked book is "
            f"long-heavy ({long_pct:.0f}/{100 - long_pct:.0f})"
        )
    if change_pct_24h > 0 and long_pct <= BOOK_SHORT_HEAVY:
        short_pct = 100.0 - long_pct
        return (
            f"price vs prev day {change_pct_24h:+.1f}% while tracked book is "
            f"short-heavy ({long_pct:.0f}/{short_pct:.0f})"
        )
    return None


def liq_direction(liq: dict[str, Any] | None, *, quiet_usd: float = LIQ_QUIET_USD) -> str:
    liq = liq or {}
    total = float(liq.get("total_usd") or 0)
    long_usd = float(liq.get("long_usd") or 0)
    short_usd = float(liq.get("short_usd") or 0)
    if total < quiet_usd:
        return "quiet"
    if long_usd > short_usd * LIQ_SKEW_RATIO:
        return "long-flush"
    if short_usd > long_usd * LIQ_SKEW_RATIO:
        return "short-flush"
    return "split"


def _book_row(snapshot: dict[str, Any], asset: str | None) -> dict[str, Any]:
    consensus = snapshot.get("top3_consensus") or {}
    if asset:
        want = asset.upper()
        for row in consensus.get("per_asset") or []:
            if str(row.get("asset") or "").upper() == want:
                return row
        return {}
    if consensus.get("long_pct") is not None:
        return {
            "asset": "Top3",
            "long_pct": consensus.get("long_pct"),
            "short_pct": consensus.get("short_pct"),
            "long_usd": sum(float(r.get("long_usd") or 0) for r in (consensus.get("per_asset") or [])),
            "short_usd": sum(float(r.get("short_usd") or 0) for r in (consensus.get("per_asset") or [])),
            "positioned": sum(int(r.get("positioned") or 0) for r in (consensus.get("per_asset") or [])),
        }
    return snapshot.get("book_wide") or {}


def _tape_row(snapshot: dict[str, Any], asset: str | None) -> dict[str, Any]:
    tape = snapshot.get("tape") or {}
    if asset:
        return tape.get(asset.upper()) or tape.get(asset) or {}
    assets = tab_assets(snapshot)
    if assets:
        return tape.get(assets[0]) or {}
    if tape:
        return next(iter(tape.values()))
    return {}


def _liq_for(snapshot: dict[str, Any], hours: int, asset: str | None) -> dict[str, Any]:
    if asset:
        by_asset = snapshot.get(f"liq_{hours}h_by_asset") or {}
        return by_asset.get(asset.upper()) or by_asset.get(asset) or {}
    return snapshot.get(f"liq_{hours}h") or {}


def _funding_pct(snapshot: dict[str, Any], asset: str | None) -> float | None:
    tape = _tape_row(snapshot, asset)
    if tape.get("funding_pct") is not None:
        try:
            return float(tape["funding_pct"])
        except (TypeError, ValueError):
            pass
    rows = snapshot.get("top3_funding") or []
    if asset:
        want = asset.upper()
        for row in rows:
            if str(row.get("asset") or "").upper() == want:
                return float(row.get("funding_pct"))
        return None
    if rows:
        return float(rows[0].get("funding_pct"))
    return None


def _book_label(long_pct: float) -> str:
    if long_pct >= BOOK_LONG_HEAVY:
        return "long-heavy"
    if long_pct <= BOOK_SHORT_HEAVY:
        return "short-heavy"
    return "no clear lean"


def strip_prefer_from_headline(headline: str) -> str:
    text = (headline or "").strip()
    text = _PREFER_TAIL_RE.sub("", text).strip(" —-")
    return text.strip()


def headline_has_prefer(headline: str) -> bool:
    return bool(_PREFER_HEADLINE_RE.search(headline or ""))


def tldr_has_prefer(tldr: BriefTldr) -> bool:
    blob = f"{tldr.now} {tldr.short_read} {tldr.however}"
    return bool(re.search(r"\bprefer\s+(longs?|shorts?)\b", blob, re.I))


def _confirm_however(snapshot: dict[str, Any], asset: str | None, long_pct: float | None) -> str:
    funding = _funding_pct(snapshot, asset)
    from app.services.inference import FUNDING_EXTREME_ABS_PCT

    lean = _book_label(float(long_pct)) if long_pct is not None else "balanced"
    extreme = funding is not None and abs(funding) >= FUNDING_EXTREME_ABS_PCT
    if extreme:
        fund_txt = f"funding is extreme ({funding:+.4f}%)"
    else:
        fund_txt = "funding is not extreme"
    return (
        f"tracked book stays {lean} and {fund_txt} "
        f"(coverage {coverage_label(snapshot)})"
    )


def _liq_24h_however(snapshot: dict[str, Any], asset: str | None) -> str | None:
    liq_1h = _liq_for(snapshot, 1, asset)
    liq_24h = _liq_for(snapshot, 24, asset)
    if liq_direction(liq_1h) != "quiet":
        return None
    direction = liq_direction(liq_24h, quiet_usd=LIQ_24H_SKEW_USD)
    if direction in {"long-flush", "short-flush"}:
        long_usd = float(liq_24h.get("long_usd") or 0)
        short_usd = float(liq_24h.get("short_usd") or 0)
        return (
            f"1h sampled liq is quiet but 24h sampled liq is {direction} "
            f"(~{format_usd_short(long_usd)} long / {format_usd_short(short_usd)} short)"
        )
    return None


def _book_wide_however(snapshot: dict[str, Any]) -> str | None:
    consensus = snapshot.get("top3_consensus") or {}
    wide = snapshot.get("book_wide") or {}
    top_pct = consensus.get("long_pct")
    wide_pct = wide.get("long_pct")
    if top_pct is None or wide_pct is None:
        return None
    if _book_label(float(top_pct)) == _book_label(float(wide_pct)):
        return None
    if BOOK_SHORT_HEAVY < float(top_pct) < BOOK_LONG_HEAVY:
        return None
    if BOOK_SHORT_HEAVY < float(wide_pct) < BOOK_LONG_HEAVY:
        return None
    return (
        f"Top3 tracked book is {_book_label(float(top_pct))} "
        f"while the wider tracked book is {_book_label(float(wide_pct))}"
    )


def _funding_vs_book_however(snapshot: dict[str, Any], asset: str | None, long_pct: float | None) -> str | None:
    from app.services.inference import FUNDING_EXTREME_ABS_PCT

    funding = _funding_pct(snapshot, asset)
    if funding is None or long_pct is None:
        return None
    if abs(funding) < FUNDING_EXTREME_ABS_PCT:
        return None
    if funding > 0 and long_pct <= BOOK_SHORT_HEAVY:
        return (
            f"funding {funding:+.4f}% (longs pay) while tracked book is short-heavy"
        )
    if funding < 0 and long_pct >= BOOK_LONG_HEAVY:
        return (
            f"funding {funding:+.4f}% (shorts pay) while tracked book is long-heavy"
        )
    return None


def pick_however(snapshot: dict[str, Any], asset: str | None = None) -> str:
    book = _book_row(snapshot, asset)
    long_pct = book.get("long_pct")
    try:
        long_val = float(long_pct) if long_pct is not None else None
    except (TypeError, ValueError):
        long_val = None
    tape = _tape_row(snapshot, asset)
    change = tape.get("change_pct_24h")
    try:
        change_val = float(change) if change is not None else None
    except (TypeError, ValueError):
        change_val = None

    tension = price_vs_book_tension(change_val, long_val)
    if tension:
        return tension
    liq24 = _liq_24h_however(snapshot, asset)
    if liq24:
        return liq24
    if not asset:
        wide = _book_wide_however(snapshot)
        if wide:
            return wide
    fund = _funding_vs_book_however(snapshot, asset, long_val)
    if fund:
        return fund
    return _confirm_however(snapshot, asset, long_val)


def build_tldr_slots(snapshot: dict[str, Any], asset: str | None = None) -> BriefTldr:
    lead = (asset or (tab_assets(snapshot)[:1] or ["Top3"])[0]).upper()
    if not asset:
        assets = tab_assets(snapshot)
        lead = "/".join(assets) if assets else "Top3"
    tape = _tape_row(snapshot, asset)
    book = _book_row(snapshot, asset)
    as_of = snapshot.get("as_of") or ""
    if isinstance(as_of, str) and "T" in as_of:
        as_of_txt = as_of.split("T")[0]
    else:
        as_of_txt = str(as_of)[:10]

    now_bits: list[str] = [str(lead)]
    mark = tape.get("mark_price")
    if mark is not None:
        try:
            now_bits.append(format_mark(float(mark)))
        except (TypeError, ValueError):
            pass
    if as_of_txt:
        now_bits.append(f"as of {as_of_txt}")
    change = tape.get("change_pct_24h")
    if change is not None:
        try:
            now_bits.append(f"vs prev day {float(change):+.1f}%")
        except (TypeError, ValueError):
            pass
    funding = _funding_pct(snapshot, asset)
    if funding is not None:
        now_bits.append(f"funding {funding:+.4f}%")
    now = " · ".join(now_bits)

    long_pct = book.get("long_pct")
    long_usd = float(book.get("long_usd") or 0)
    short_usd = float(book.get("short_usd") or 0)
    try:
        lp = float(long_pct) if long_pct is not None else None
    except (TypeError, ValueError):
        lp = None
    if lp is None and (long_usd + short_usd) > 0:
        lp = long_usd / (long_usd + short_usd) * 100.0
    sp = (100.0 - lp) if lp is not None else None
    label = _book_label(lp) if lp is not None else "thin book"
    liq_1h = _liq_for(snapshot, 1, asset)
    liq_dir = liq_direction(liq_1h)
    liq_txt = f"sampled 1h liq {liq_dir}"
    if liq_dir != "quiet":
        liq_txt += f" (~{format_usd_short(float(liq_1h.get('total_usd') or 0))})"
    if lp is not None and sp is not None:
        short_read = (
            f"{label}: tracked book {format_usd_short(long_usd)} long / "
            f"{format_usd_short(short_usd)} short ({lp:.0f}/{sp:.0f}) and {liq_txt}"
        )
    else:
        short_read = f"{label}: tracked book still thin and {liq_txt}"

    however = pick_however(snapshot, asset)
    return BriefTldr(now=now, short_read=short_read, however=however)


def slice_snapshot(snapshot: dict[str, Any], asset: str) -> dict[str, Any]:
    want = asset.upper()
    market_tabs = tab_assets(snapshot)
    consensus = dict(snapshot.get("top3_consensus") or {})
    per_asset = [
        row
        for row in (consensus.get("per_asset") or [])
        if str(row.get("asset") or "").upper() == want
    ]
    row0 = per_asset[0] if per_asset else {}
    consensus["assets"] = [want]
    consensus["per_asset"] = per_asset
    if row0:
        consensus["long_pct"] = row0.get("long_pct")
        consensus["short_pct"] = row0.get("short_pct")
        lp = float(row0.get("long_pct") or 50)
        if lp >= BOOK_LONG_HEAVY:
            consensus["mood"] = "BULLISH"
        elif lp <= BOOK_SHORT_HEAVY:
            consensus["mood"] = "BEARISH"
        else:
            consensus["mood"] = "NEUTRAL"
        consensus["reason"] = (
            f"{want} tracked book {row0.get('long_pct')}% long / {row0.get('short_pct')}% short"
        )

    tape = snapshot.get("tape") or {}
    tape_one = {}
    if want in tape:
        tape_one = {want: tape[want]}
    elif asset in tape:
        tape_one = {want: tape[asset]}

    sliced = dict(snapshot)
    sliced["top3_consensus"] = consensus
    sliced["tape"] = tape_one
    sliced["coin_stances"] = [
        row
        for row in (snapshot.get("coin_stances") or [])
        if str(row.get("asset") or "").upper() == want
    ]
    sliced["top3_funding"] = [
        row
        for row in (snapshot.get("top3_funding") or [])
        if str(row.get("asset") or "").upper() == want
    ]
    sliced["extreme_funding"] = [
        row
        for row in (snapshot.get("extreme_funding") or [])
        if str(row.get("asset") or "").upper() == want
    ]
    sliced["biggest_positions"] = [
        row
        for row in (snapshot.get("biggest_positions") or [])
        if str(row.get("asset") or "").upper() == want
    ]
    liq1 = (snapshot.get("liq_1h_by_asset") or {}).get(want) or {}
    liq24 = (snapshot.get("liq_24h_by_asset") or {}).get(want) or {}
    sliced["liq_1h"] = liq1
    sliced["liq_24h"] = liq24
    sliced["liq_1h_by_asset"] = {want: liq1} if liq1 else {}
    sliced["liq_24h_by_asset"] = {want: liq24} if liq24 else {}
    positioned = int(row0.get("positioned") or 0)
    tracked = int((snapshot.get("coverage") or {}).get("tracked") or 0)
    sliced["coverage"] = {"positioned": positioned, "tracked": tracked}
    sliced["_market_tabs"] = market_tabs
    return sliced


def apply_tldr_to_brief(brief: Any, snapshot: dict[str, Any], asset: str | None = None) -> Any:
    """Attach rule TL;DR, strip Prefer from headline, set stale/tabs."""
    tldr = build_tldr_slots(snapshot, asset)
    headline = strip_prefer_from_headline(brief.headline)
    if not headline or headline_has_prefer(headline):
        headline = tldr.now
    return brief.model_copy(
        update={
            "tldr": tldr,
            "headline": headline[:240],
            "asset": asset.upper() if asset else None,
            "stale": snapshot_stale(snapshot),
            "tab_assets": list(snapshot.get("_market_tabs") or tab_assets(snapshot)),
        }
    )
