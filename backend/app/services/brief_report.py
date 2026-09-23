"""Rule-based Market Brief TL;DR, tape, and coin slicing (no LLM)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.schemas import BriefDigest, BriefStance, BriefTldr

BOOK_LONG_HEAVY = 58.0
BOOK_SHORT_HEAVY = 42.0
TENSION_MIN_ABS_PCT = 1.0
STALE_AFTER = timedelta(minutes=45)
LIQ_QUIET_USD = 250_000.0
LIQ_SKEW_RATIO = 1.5
LIQ_24H_SKEW_USD = 1_000_000.0
# Hyperliquid pays funding hourly; metaAndAssetCtxs.funding is that 1h rate.
FUNDING_INTERVAL_LABEL = "1h"
COVERAGE_HIGH_PCT = 70.0
COVERAGE_MEDIUM_PCT = 40.0
COVERAGE_LEGEND = (
    "Low <40% · Medium 40–69% · High ≥70% of tracked whales with open positions"
)
TAPE_LEAD_PREFERENCE = ("BTC", "ETH", "SOL", "HYPE")

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
        return f"${abs_v / 1_000_000_000:.2f}B"
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


def coverage_counts(snapshot: dict[str, Any]) -> tuple[int, int]:
    cov = snapshot.get("coverage") or {}
    return int(cov.get("positioned") or 0), int(cov.get("tracked") or 0)


def coverage_band(snapshot: dict[str, Any]) -> str:
    positioned, tracked = coverage_counts(snapshot)
    if tracked <= 0:
        return "Low"
    pct = positioned / tracked * 100.0
    if pct >= COVERAGE_HIGH_PCT:
        return "High"
    if pct >= COVERAGE_MEDIUM_PCT:
        return "Medium"
    return "Low"


def coverage_label(snapshot: dict[str, Any]) -> str:
    positioned, tracked = coverage_counts(snapshot)
    return f"{positioned}/{tracked} ({coverage_band(snapshot)})"


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


def _lead_tape_asset(snapshot: dict[str, Any], asset: str | None) -> str | None:
    if asset:
        return asset.upper()
    assets = tab_assets(snapshot)
    for preferred in TAPE_LEAD_PREFERENCE:
        if preferred in assets:
            return preferred
    return assets[0] if assets else None


def _tape_row(snapshot: dict[str, Any], asset: str | None) -> dict[str, Any]:
    tape = snapshot.get("tape") or {}
    lead = _lead_tape_asset(snapshot, asset)
    if lead:
        return tape.get(lead) or tape.get(lead.lower()) or {}
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
    lead = _lead_tape_asset(snapshot, asset) or "Top3"
    tape = _tape_row(snapshot, asset)
    book = _book_row(snapshot, asset)
    as_of = snapshot.get("as_of") or ""
    if isinstance(as_of, str) and "T" in as_of:
        as_of_txt = as_of.split("T")[0]
    else:
        as_of_txt = str(as_of)[:10]

    now_bits: list[str] = []
    mark = tape.get("mark_price")
    if mark is not None:
        try:
            now_bits.append(f"{lead} {format_mark(float(mark))}")
        except (TypeError, ValueError):
            now_bits.append(str(lead))
    else:
        now_bits.append(str(lead))
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
        now_bits.append(f"funding ({FUNDING_INTERVAL_LABEL}) {funding:+.4f}%")
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


def _long_short_pct(book: dict[str, Any]) -> tuple[float | None, float | None]:
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
    return lp, sp


def _net_usd_clause(long_usd: float, short_usd: float) -> str:
    net = long_usd - short_usd
    if abs(net) < 1:
        return ""
    if net < 0:
        return f" (net short ~{format_usd_short(abs(net))})"
    return f" (net long ~{format_usd_short(net)})"


def _as_of_date(snapshot: dict[str, Any]) -> str:
    as_of = snapshot.get("as_of") or ""
    if isinstance(as_of, str) and "T" in as_of:
        return as_of.split("T")[0]
    return str(as_of)[:10]


def _per_asset_rows(snapshot: dict[str, Any], asset: str | None) -> list[dict[str, Any]]:
    if asset:
        row = _book_row(snapshot, asset)
        return [row] if row else []
    return list((snapshot.get("top3_consensus") or {}).get("per_asset") or [])


def _dominant_share_bit(row: dict[str, Any]) -> str | None:
    name = str(row.get("asset") or "").upper()
    lp, sp = _long_short_pct(row)
    if not name or lp is None or sp is None:
        return None
    if sp >= lp:
        return f"{name} {sp:.1f}% short"
    return f"{name} {lp:.1f}% long"


def build_as_of_line(snapshot: dict[str, Any], asset: str | None = None) -> str:
    lead = _lead_tape_asset(snapshot, asset) or "Top3"
    tape = _tape_row(snapshot, asset)
    date = _as_of_date(snapshot)
    bits: list[str] = []
    if date:
        bits.append(f"As of {date}")
    mark = tape.get("mark_price")
    price_bit = str(lead)
    if mark is not None:
        try:
            price_bit = f"{lead} {format_mark(float(mark))}"
        except (TypeError, ValueError):
            pass
    change = tape.get("change_pct_24h")
    if change is not None:
        try:
            price_bit = f"{price_bit} ({float(change):+.1f}% vs prev day)"
        except (TypeError, ValueError):
            pass
    bits.append(price_bit)
    return " | ".join(bits)


def build_funding_line(snapshot: dict[str, Any], asset: str | None = None) -> str:
    funding = _funding_pct(snapshot, asset)
    if funding is None:
        return ""
    return f"Funding ({FUNDING_INTERVAL_LABEL}) {funding:+.4f}%"


def build_positioning_lines(snapshot: dict[str, Any], asset: str | None = None) -> list[str]:
    book = _book_row(snapshot, asset)
    lp, sp = _long_short_pct(book)
    long_usd = float(book.get("long_usd") or 0)
    short_usd = float(book.get("short_usd") or 0)
    lines: list[str] = []
    if lp is not None and sp is not None:
        lines.append(
            f"Tracked book: {lp:.0f}% long / {sp:.0f}% short"
            f"{_net_usd_clause(long_usd, short_usd)}"
        )
    if not asset:
        bits = [
            bit
            for row in _per_asset_rows(snapshot, None)
            if (bit := _dominant_share_bit(row))
        ]
        if bits:
            lines.append("By asset: " + " · ".join(bits))
    liq_1h = _liq_for(snapshot, 1, asset)
    liq_dir = liq_direction(liq_1h)
    if liq_dir == "quiet":
        lines.append("Liquidations (1h): quiet")
    else:
        total = format_usd_short(float(liq_1h.get("total_usd") or 0))
        lines.append(f"Liquidations (1h): {liq_dir} (~{total})")
    lines.append(f"Coverage: {coverage_label(snapshot)}")
    return lines


def _funding_extreme(snapshot: dict[str, Any], asset: str | None) -> bool:
    from app.services.inference import FUNDING_EXTREME_ABS_PCT

    funding = _funding_pct(snapshot, asset)
    return funding is not None and abs(funding) >= FUNDING_EXTREME_ABS_PCT


def build_read(snapshot: dict[str, Any], asset: str | None, stance: BriefStance) -> str:
    book = _book_row(snapshot, asset)
    lp, _ = _long_short_pct(book)
    lean = _book_label(lp) if lp is not None else "thin"
    band = coverage_band(snapshot)
    extreme = _funding_extreme(snapshot, asset)
    fund_txt = (
        "funding is extreme"
        if extreme
        else "funding not at extreme levels"
    )

    rows = _per_asset_rows(snapshot, asset)
    leans = []
    for row in rows:
        row_lp, _ = _long_short_pct(row)
        if row_lp is not None:
            leans.append(_book_label(row_lp))
    same_lean = bool(leans) and all(item == leans[0] for item in leans)
    n_assets = len(leans)

    if lean == "thin":
        head = f"Tracked book is still thin, {fund_txt}."
    elif asset:
        head = f"Tracked {asset} book stays {lean}, {fund_txt}."
    elif same_lean and lean in {"short-heavy", "long-heavy"} and n_assets >= 2:
        head = f"Book stays {lean} across all {n_assets} assets, {fund_txt}."
    elif lean == "no clear lean":
        head = f"Book has no clear lean across Top3, {fund_txt}."
    else:
        head = f"Top3 book is {lean} with mixed coin skew, {fund_txt}."

    if band == "Low":
        cov_txt = "Low coverage — treat as a weak sample, not a high-confidence signal."
        if stance == BriefStance.WAIT or lean == "no clear lean":
            cov_txt = "Low coverage — wait for a denser sample before leaning."
    elif band == "Medium":
        if stance == BriefStance.WAIT or lean == "no clear lean":
            cov_txt = "Medium coverage — no clean directional signal yet."
        else:
            cov_txt = "Medium coverage — directional signal present but not high-confidence."
    else:
        if stance == BriefStance.WAIT or lean == "no clear lean":
            cov_txt = "High coverage — still no clean lean, so this is not confirmation."
        else:
            cov_txt = (
                "High coverage — lean is usable as a positioning signal, "
                "still not confirmation."
            )

    tension = None
    tape = _tape_row(snapshot, asset)
    change = tape.get("change_pct_24h")
    try:
        change_val = float(change) if change is not None else None
    except (TypeError, ValueError):
        change_val = None
    tension = price_vs_book_tension(change_val, lp)
    bits = [head, cov_txt]
    if tension:
        bits.append(f"Also: {tension}.")
    return " ".join(bits)


def build_note(snapshot: dict[str, Any], asset: str | None, stance: BriefStance) -> str:
    names: list[str] = []
    want_heavy = (
        "short-heavy" if stance == BriefStance.PREFER_SHORT else "long-heavy"
    )
    for row in _per_asset_rows(snapshot, asset):
        lp, _ = _long_short_pct(row)
        if lp is None:
            continue
        if _book_label(lp) == want_heavy:
            name = str(row.get("asset") or "").upper()
            if name:
                names.append(name)

    if stance == BriefStance.PREFER_SHORT:
        if names:
            return (
                f"Whale book skews short on {'/'.join(names)}; "
                "positioning supports short bias, not confirmation."
            )
        return "Positioning supports short bias, not confirmation."
    if stance == BriefStance.PREFER_LONG:
        if names:
            return (
                f"Whale book skews long on {'/'.join(names)}; "
                "positioning supports long bias, not confirmation."
            )
        return "Positioning supports long bias, not confirmation."
    return "Positioning is split — no confirmation either way."


def build_brief_digest(
    snapshot: dict[str, Any],
    asset: str | None,
    stance: BriefStance,
) -> BriefDigest:
    return BriefDigest(
        as_of_line=build_as_of_line(snapshot, asset),
        funding_line=build_funding_line(snapshot, asset),
        positioning=build_positioning_lines(snapshot, asset),
        read=build_read(snapshot, asset, stance),
        note=build_note(snapshot, asset, stance),
        coverage_band=coverage_band(snapshot),
    )


def apply_tldr_to_brief(brief: Any, snapshot: dict[str, Any], asset: str | None = None) -> Any:
    """Attach rule TL;DR + labeled digest, strip Prefer from headline, set stale/tabs."""
    tldr = build_tldr_slots(snapshot, asset)
    digest = build_brief_digest(snapshot, asset, brief.stance)
    headline = strip_prefer_from_headline(brief.headline)
    if not headline or headline_has_prefer(headline):
        headline = tldr.now
    return brief.model_copy(
        update={
            "tldr": tldr,
            "digest": digest,
            "headline": headline[:240],
            "asset": asset.upper() if asset else None,
            "stale": snapshot_stale(snapshot),
            "tab_assets": list(snapshot.get("_market_tabs") or tab_assets(snapshot)),
        }
    )
