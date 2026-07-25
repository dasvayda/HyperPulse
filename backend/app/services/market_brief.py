"""Market Brief: structured snapshot + periodic LLM desk commentary."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.db import SessionLocal
from app.models.orm import MarketBriefRow
from app.models.schemas import BriefStance, InsightStance, MarketBrief
from app.services.store import store
from app.services.whale_book import list_biggest_positions

logger = logging.getLogger(__name__)

BRIEF_COOLDOWN = timedelta(seconds=max(60, settings.market_brief_cooldown_seconds))
ALLOWED_STRATEGIES = {
    "Speculative",
    "Directional",
    "Diversified",
    "Scalping",
    "Momentum",
    "Mean Reversion",
    "Funding Arbitrage",
    "Swing Trading",
    "Trend Following",
    "Mixed",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_usd_short(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1_000_000_000:
        return f"${abs_v / 1_000_000_000:.1f}B"
    if abs_v >= 1_000_000:
        return f"${abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"${abs_v / 1_000:.1f}K"
    return f"${abs_v:.0f}"


def canonicalize_strategy(raw: str) -> str:
    """Collapse LLM free-text strategy labels into a fixed enum."""
    text = (raw or "").strip()
    if not text:
        return "Mixed"
    lower = text.lower().replace("_", " ").replace("-", " ")
    if lower in {"undefined", "none", "inactive", "n/a", "na", "null"}:
        return "Mixed"
    if any(k in lower for k in ("speculat", "high risk", "highrisk", "high lev", "high leverage")):
        return "Speculative"
    if "scalp" in lower or "high frequency" in lower or "high-frequency" in lower:
        return "Scalping"
    if "mean" in lower and "reversion" in lower:
        return "Mean Reversion"
    if "funding" in lower or "arb" in lower:
        return "Funding Arbitrage"
    if "momentum" in lower or "breakout" in lower:
        return "Momentum"
    if "swing" in lower:
        return "Swing Trading"
    if "trend" in lower:
        return "Trend Following"
    if "diversif" in lower or "multi asset" in lower or "multi-asset" in lower:
        return "Diversified"
    if "direction" in lower or "concentrat" in lower or "one coin" in lower:
        return "Directional"
    if "passive" in lower or "long term" in lower or "long-term" in lower:
        return "Mixed"
    # Title-case exact match against allowlist
    titled = " ".join(w.capitalize() for w in lower.split())
    for allowed in ALLOWED_STRATEGIES:
        if allowed.lower() == lower or allowed == titled:
            return allowed
    return "Mixed"


def _top_assets_by_volume(n: int = 3) -> list[str]:
    from app.services.alerts import _top_assets_by_volume as _top

    return _top(n)


def _liq_window_usd(hours: float) -> dict[str, float | int]:
    now = _utcnow()
    cutoff = now - timedelta(hours=hours)
    long_usd = 0.0
    short_usd = 0.0
    events = 0
    for event in store.liquidation_events:
        ts = event.timestamp
        if isinstance(ts, datetime) and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        try:
            if ts < cutoff:
                continue
        except TypeError:
            continue
        events += 1
        if event.side.value == "long":
            long_usd += event.size_usd
        else:
            short_usd += event.size_usd
    return {
        "long_usd": round(long_usd, 2),
        "short_usd": round(short_usd, 2),
        "total_usd": round(long_usd + short_usd, 2),
        "events": events,
    }


ALLOWED_EVIDENCE_REFS = frozenset(
    {
        "top3_consensus",
        "coin_stances",
        "extreme_funding",
        "top3_funding",
        "liq_1h",
        "liq_24h",
        "biggest_positions",
        "coverage",
        "book_wide",
    }
)

_DIRECTIONAL_HINT = re.compile(
    r"\b(prefer\s+longs?|prefer\s+shorts?|shorting|longing|go\s+long|go\s+short|"
    r"entry\s+points?|bullish\s+signal|bearish\s+signal|"
    r"long\s+positions?|short\s+positions?)\b",
    re.I,
)
_LONG_HINT = re.compile(
    r"\b(prefer\s+longs?|longing|go\s+long|long\s+positions?|bullish\s+signal)\b",
    re.I,
)
_SHORT_HINT = re.compile(
    r"\b(prefer\s+shorts?|shorting|go\s+short|short\s+positions?|bearish\s+signal)\b",
    re.I,
)


def _funding_note(funding_pct: float) -> str:
    if funding_pct >= 0:
        return "longs pay shorts (longs crowded when extreme+)"
    return "shorts pay longs (shorts crowded when extreme-)"


def _asset_funding_pct(asset: str) -> float | None:
    tick = (store.market_ticks or {}).get(asset) or {}
    rate = tick.get("funding_rate")
    if rate is None:
        return None
    try:
        return float(rate) * 100.0
    except (TypeError, ValueError):
        return None


def _extreme_funding_rows() -> list[dict[str, Any]]:
    from app.services.inference import FUNDING_EXTREME_ABS_PCT, FUNDING_LIQUID_TOP_N

    ticks = store.market_ticks or {}
    rows: list[tuple[str, float, float]] = []
    for asset, tick in ticks.items():
        rate = tick.get("funding_rate")
        if rate is None:
            continue
        try:
            funding_pct = float(rate) * 100.0
            volume_usd = float(tick.get("day_volume_usd") or 0.0)
        except (TypeError, ValueError):
            continue
        rows.append((str(asset), funding_pct, volume_usd))
    if not rows:
        return []
    rows.sort(key=lambda item: item[2], reverse=True)
    liquid = rows[:FUNDING_LIQUID_TOP_N]
    extreme = [r for r in liquid if abs(r[1]) >= FUNDING_EXTREME_ABS_PCT]
    extreme.sort(key=lambda item: abs(item[1]), reverse=True)
    out: list[dict[str, Any]] = []
    for asset, funding_pct, _ in extreme[:3]:
        out.append(
            {
                "asset": asset,
                "funding_pct": round(funding_pct, 4),
                "note": _funding_note(funding_pct),
            }
        )
    return out


def _top3_funding_rows(assets: list[str]) -> list[dict[str, Any]]:
    """Always include Top3 funding so empty extreme_funding is not 'missing data'."""
    from app.services.inference import FUNDING_EXTREME_ABS_PCT

    out: list[dict[str, Any]] = []
    for asset in assets:
        funding_pct = _asset_funding_pct(asset)
        if funding_pct is None:
            continue
        out.append(
            {
                "asset": asset,
                "funding_pct": round(funding_pct, 4),
                "is_extreme": abs(funding_pct) >= FUNDING_EXTREME_ABS_PCT,
                "note": _funding_note(funding_pct),
            }
        )
    return out


def _top3_per_asset_book(assets: list[str]) -> list[dict[str, Any]]:
    summary = store.whale_summary
    if not summary or not summary.by_asset:
        return []
    rows: list[dict[str, Any]] = []
    for asset in assets:
        bucket = summary.by_asset.get(asset)
        if not bucket:
            continue
        rows.append(
            {
                "asset": asset,
                "long_pct": round(bucket.long_pct, 1),
                "short_pct": round(max(0.0, 100.0 - bucket.long_pct), 1),
                "long_usd": round(bucket.long_notional_usd, 2),
                "short_usd": round(bucket.short_notional_usd, 2),
                "positioned": bucket.whales,
            }
        )
    return rows


def _book_wide_block() -> dict[str, Any] | None:
    summary = store.whale_summary
    if not summary or summary.with_positions <= 0:
        return None
    return {
        "long_pct": round(summary.long_pct, 1),
        "short_pct": round(max(0.0, 100.0 - summary.long_pct), 1),
        "long_usd": round(summary.long_notional_usd, 2),
        "short_usd": round(summary.short_notional_usd, 2),
        "net_usd": round(summary.net_notional_usd, 2),
        "net_bias": summary.net_bias,
        "positioned": summary.with_positions,
        "tracked": summary.tracked,
    }


def _coin_stance_summaries() -> list[dict[str, Any]]:
    """Compact stance rows aligned with BL-02 evidence cards."""
    from app.services.inference import _build_coin_stance_insights

    cards = _build_coin_stance_insights(_utcnow())
    rows: list[dict[str, Any]] = []
    for card in cards:
        action = "wait"
        if card.stance == InsightStance.BUY:
            action = "prefer_long"
        elif card.stance == InsightStance.SELL:
            action = "prefer_short"
        rows.append(
            {
                "asset": card.asset,
                "stance": action,
                "title": card.title,
                "signals": card.signals[:3],
                "confidence": card.confidence,
            }
        )
    return rows


def _top3_consensus_block() -> dict[str, Any]:
    from app.services.alerts import compute_market_consensus, _top_assets_by_volume

    assets = _top_assets_by_volume(3)
    per_asset = _top3_per_asset_book(assets)
    computed = compute_market_consensus()
    if not computed:
        return {
            "assets": assets,
            "per_asset": per_asset,
            "mood": "NEUTRAL",
            "long_pct": None,
            "short_pct": None,
            "reason": "No whale book yet",
        }
    mood, reason, long_pct = computed
    return {
        "assets": assets,
        "per_asset": per_asset,
        "mood": mood,
        "long_pct": round(long_pct, 1),
        "short_pct": round(max(0.0, 100.0 - long_pct), 1),
        "reason": reason,
    }


def build_market_brief_snapshot() -> dict[str, Any]:
    summary = store.whale_summary
    coverage = {
        "positioned": summary.with_positions if summary else 0,
        "tracked": summary.tracked if summary else len(store.traders),
    }
    biggest = []
    try:
        traders_by_addr = {t.address: t.alias for t in store.traders}
        marks: dict[str, float] = {}
        for asset, tick in (store.market_ticks or {}).items():
            mark = tick.get("mark_price")
            if mark is not None:
                try:
                    marks[asset] = float(mark)
                except (TypeError, ValueError):
                    pass
        for pos in list_biggest_positions(
            store.whale_positions,
            traders_by_addr=traders_by_addr,
            marks=marks,
            limit=3,
        ):
            biggest.append(
                {
                    "asset": pos.asset,
                    "side": pos.side.value,
                    "size_usd": round(pos.size_usd, 2),
                    "alias": pos.trader_alias,
                }
            )
    except Exception:
        logger.exception("biggest positions for brief snapshot failed")

    consensus = _top3_consensus_block()
    assets = list(consensus.get("assets") or [])
    payload = {
        "as_of": _utcnow().isoformat(),
        "top3_consensus": consensus,
        "book_wide": _book_wide_block(),
        "coin_stances": _coin_stance_summaries(),
        "top3_funding": _top3_funding_rows(assets),
        "extreme_funding": _extreme_funding_rows(),
        "liq_1h": _liq_window_usd(1),
        "liq_24h": _liq_window_usd(24),
        "biggest_positions": biggest,
        "coverage": coverage,
    }
    # Hash without as_of so clock alone does not force regen.
    hash_body = {k: v for k, v in payload.items() if k != "as_of"}
    digest = hashlib.sha256(
        json.dumps(hash_body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    payload["snapshot_hash"] = digest
    return payload


def _snapshot_tickers(snapshot: dict[str, Any]) -> set[str]:
    tickers: set[str] = set()
    consensus = snapshot.get("top3_consensus") or {}
    for asset in consensus.get("assets") or []:
        tickers.add(str(asset).upper())
    for row in consensus.get("per_asset") or []:
        if row.get("asset"):
            tickers.add(str(row["asset"]).upper())
    for row in snapshot.get("coin_stances") or []:
        if row.get("asset"):
            tickers.add(str(row["asset"]).upper())
    for row in snapshot.get("extreme_funding") or []:
        if row.get("asset"):
            tickers.add(str(row["asset"]).upper())
    for row in snapshot.get("top3_funding") or []:
        if row.get("asset"):
            tickers.add(str(row["asset"]).upper())
    for row in snapshot.get("biggest_positions") or []:
        if row.get("asset"):
            tickers.add(str(row["asset"]).upper())
    return tickers


def _rule_majority_stance(snapshot: dict[str, Any]) -> BriefStance | None:
    """Clear majority among coin_stances, else None."""
    stances = [r.get("stance") for r in (snapshot.get("coin_stances") or []) if r.get("stance")]
    if not stances:
        consensus = snapshot.get("top3_consensus") or {}
        mood = str(consensus.get("mood") or "")
        if "BULL" in mood:
            return BriefStance.PREFER_LONG
        if "BEAR" in mood:
            return BriefStance.PREFER_SHORT
        return None
    buys = sum(1 for s in stances if s == "prefer_long")
    sells = sum(1 for s in stances if s == "prefer_short")
    if buys >= 2 and buys > sells:
        return BriefStance.PREFER_LONG
    if sells >= 2 and sells > buys:
        return BriefStance.PREFER_SHORT
    if buys == 1 and sells == 0 and len(stances) == 1:
        return BriefStance.PREFER_LONG
    if sells == 1 and buys == 0 and len(stances) == 1:
        return BriefStance.PREFER_SHORT
    return None


def _text_has_unknown_ticker(text: str, allowed: set[str]) -> bool:
    # Catch ALLCAPS tickers 2–10 chars that look like assets.
    for match in re.findall(r"\b([A-Z]{2,10})\b", text):
        if match in {"USD", "ROI", "OI", "BTC", "ETH", "SOL", "HL", "API", "LLM"}:
            if match in allowed or match in {"USD", "ROI", "OI", "HL", "API", "LLM"}:
                continue
        if match not in allowed and match not in {"USD", "ROI", "OI", "HL", "API", "LLM", "TOP"}:
            # Allow BTC/ETH/SOL always as majors even if ticks empty
            if match in {"BTC", "ETH", "SOL"}:
                continue
            return True
    return False


def _filter_bullets(
    bullets: list[str],
    allowed: set[str],
    *,
    stance: BriefStance | None = None,
) -> list[str]:
    clean: list[str] = []
    for item in bullets:
        text = str(item).strip()
        if not text or len(text) > 220:
            continue
        if _text_has_unknown_ticker(text, allowed):
            continue
        if stance == BriefStance.WAIT and _DIRECTIONAL_HINT.search(text):
            continue
        if stance == BriefStance.PREFER_SHORT and _LONG_HINT.search(text):
            continue
        if stance == BriefStance.PREFER_LONG and _SHORT_HINT.search(text):
            continue
        clean.append(text)
        if len(clean) >= 3:
            break
    return clean


def _normalize_evidence_refs(raw: Any, snapshot: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            key = str(item).strip().lower().replace(" ", "_")
            if key in ALLOWED_EVIDENCE_REFS and key not in refs:
                refs.append(key)
    if refs:
        return refs[:6]
    # Derive from what the snapshot actually has.
    defaults: list[str] = []
    if snapshot.get("top3_consensus"):
        defaults.append("top3_consensus")
    if snapshot.get("coin_stances"):
        defaults.append("coin_stances")
    if snapshot.get("extreme_funding"):
        defaults.append("extreme_funding")
    elif snapshot.get("top3_funding"):
        defaults.append("top3_funding")
    if float((snapshot.get("liq_1h") or {}).get("total_usd") or 0) > 0:
        defaults.append("liq_1h")
    if snapshot.get("book_wide"):
        defaults.append("book_wide")
    return defaults[:6] or ["top3_consensus"]


def _status_too_thin(status: str) -> bool:
    text = status.strip()
    if len(text) < 80:
        return True
    if text.lower() in {"bearish", "bullish", "neutral", "wait", "prefer long", "prefer short"}:
        return True
    return False


def build_template_brief(snapshot: dict[str, Any]) -> MarketBrief:
    consensus = snapshot.get("top3_consensus") or {}
    mood = str(consensus.get("mood") or "NEUTRAL")
    reason = str(consensus.get("reason") or "Whale book warming up.")
    assets = consensus.get("assets") or []
    asset_label = "/".join(assets) if assets else "majors"
    long_pct = consensus.get("long_pct")
    stances = snapshot.get("coin_stances") or []
    funding = snapshot.get("extreme_funding") or []
    liq = snapshot.get("liq_1h") or {}

    majority = _rule_majority_stance(snapshot)
    if majority is None:
        if "BULL" in mood:
            stance = BriefStance.PREFER_LONG
        elif "BEAR" in mood:
            stance = BriefStance.PREFER_SHORT
        else:
            stance = BriefStance.WAIT
    else:
        stance = majority

    stance_label = {
        BriefStance.PREFER_LONG: "Prefer longs",
        BriefStance.PREFER_SHORT: "Prefer shorts",
        BriefStance.WAIT: "Wait",
    }[stance]

    if long_pct is not None:
        if "NEUTRAL" in mood.upper():
            lean_txt = "balanced (no clear lean)"
        elif "BULL" in mood.upper():
            lean_txt = "lean long"
        elif "BEAR" in mood.upper():
            lean_txt = "lean short"
        else:
            lean_txt = f"lean {mood.replace('_', ' ').title()}"
        headline = f"Top3 ({asset_label}) whales {lean_txt} — {stance_label}"
    else:
        headline = f"Market brief: {stance_label} while whale coverage builds"

    status_bits: list[str] = []
    if long_pct is not None:
        short_pct = 100.0 - float(long_pct)
        if "NEUTRAL" in mood.upper():
            status_bits.append(
                f"Top3 whale book remains {float(long_pct):.0f}% long / {short_pct:.0f}% short (balanced), "
                f"driven by positioning rather than a single catalyst. {reason}"
            )
        elif "BEAR" in mood.upper():
            status_bits.append(
                f"Top3 whale book remains {short_pct:.0f}% short / {float(long_pct):.0f}% long, "
                f"signaling near-term sell-side pressure from tracked-whale inventory. {reason}"
            )
        else:
            status_bits.append(
                f"Top3 whale book remains {float(long_pct):.0f}% long / {short_pct:.0f}% short, "
                f"signaling near-term buy-side pressure from tracked-whale inventory. {reason}"
            )
    else:
        status_bits.append(reason)
    if stances:
        bits = [
            f"{s['asset']} {s['stance'].replace('_', ' ')}"
            for s in stances[:3]
            if s.get("asset")
        ]
        if bits:
            status_bits.append(
                "What matters on coin calls: " + "; ".join(bits) + "."
            )
    if funding:
        f0 = funding[0]
        status_bits.append(
            f"Extreme funding on {f0['asset']} at {f0['funding_pct']:+.3f}% — {f0['note']}."
        )
    else:
        top3_f = snapshot.get("top3_funding") or []
        if top3_f:
            status_bits.append(
                "Top3 funding stays near flat — not a crowded-funding story."
            )
    liq_total = float(liq.get("total_usd") or 0)
    if liq_total > 0:
        long_liq = float(liq.get("long_usd") or 0)
        short_liq = float(liq.get("short_usd") or 0)
        if long_liq > short_liq * 1.5:
            liq_read = "tends to read as a long flush"
        elif short_liq > long_liq * 1.5:
            liq_read = "tends to read as a short flush"
        else:
            liq_read = "no clean liq skew"
        status_bits.append(
            f"Last 1h liquidations {_format_usd_short(liq_total)} "
            f"(long {_format_usd_short(long_liq)} / short {_format_usd_short(short_liq)}), "
            f"{liq_read}."
        )
    cov = snapshot.get("coverage") or {}
    status_bits.append(
        f"Coverage: {cov.get('positioned', 0)}/{cov.get('tracked', 0)} tracked whales positioned."
    )

    suggestions: list[str] = []
    if stance == BriefStance.PREFER_SHORT:
        suggestions.append(f"Prefer shorts on {asset_label} while Top3 whale book stays short-heavy.")
    elif stance == BriefStance.PREFER_LONG:
        suggestions.append(f"Prefer longs on {asset_label} while Top3 whale book stays long-heavy.")
    else:
        suggestions.append("Wait for a clearer Top3 whale or coin-stance agreement before sizing up.")
    if funding:
        f0 = funding[0]
        if f0["funding_pct"] < 0:
            suggestions.append(
                f"Watch {f0['asset']} for short-squeeze risk (extreme negative funding)."
            )
        else:
            suggestions.append(
                f"Watch {f0['asset']} for long-flush risk (extreme positive funding)."
            )
    if stances:
        lead = stances[0]
        suggestions.append(
            f"Size off {lead['asset']} evidence card ({lead['stance'].replace('_', ' ')})."
        )

    risks = [
        "Not financial advice — Hyperliquid tracked-whale sample, not the full market.",
        "Thin coverage or fast funding flips can invalidate this read within the hour.",
    ]
    if majority and stance != majority:
        risks.insert(0, "Signals conflict across coins — treat direction as wait-leaning.")

    refs = ["top3_consensus", "coverage"]
    if snapshot.get("book_wide"):
        refs.append("book_wide")
    if stances:
        refs.append("coin_stances")
    if funding:
        refs.append("extreme_funding")
    elif snapshot.get("top3_funding"):
        refs.append("top3_funding")
    if liq_total > 0:
        refs.append("liq_1h")

    return MarketBrief(
        headline=headline[:240],
        market_status=" ".join(status_bits),
        stance=stance,
        suggestions=suggestions[:3],
        risks=risks[:3],
        evidence_refs=refs,
        as_of=_utcnow(),
        provider="template",
        source="template",
        snapshot_hash=str(snapshot.get("snapshot_hash") or ""),
    )


def _parse_stance(raw: Any) -> BriefStance:
    text = str(raw or "wait").lower().replace(" ", "_").replace("-", "_")
    if text in {"prefer_long", "preferlongs", "buy", "long", "bullish"}:
        return BriefStance.PREFER_LONG
    if text in {"prefer_short", "prefershorts", "sell", "short", "bearish"}:
        return BriefStance.PREFER_SHORT
    return BriefStance.WAIT


def _clean_text(text: str) -> str:
    # Models sometimes emit control chars instead of em-dash.
    text = re.sub(r"[\x00-\x1f]", " - ", text)
    text = re.sub(r"\s+-\s+", " — ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # "mixed" is reserved for trader Strategy tags — rewrite book/mood wording.
    text = re.sub(r"\bmixed\b", "balanced", text, flags=re.I)
    return text


def _validate_brief(data: dict[str, Any], snapshot: dict[str, Any], provider: str) -> MarketBrief | None:
    allowed = _snapshot_tickers(snapshot)
    headline = _clean_text(str(data.get("headline") or ""))
    status = _clean_text(str(data.get("market_status") or ""))
    if not headline or not status:
        return None
    if _status_too_thin(status):
        return None
    if _text_has_unknown_ticker(headline, allowed) or _text_has_unknown_ticker(status, allowed):
        return None

    original_stance = _parse_stance(data.get("stance"))
    stance = original_stance
    majority = _rule_majority_stance(snapshot)
    forced_wait = False
    if majority and stance != majority and stance != BriefStance.WAIT:
        stance = BriefStance.WAIT
        forced_wait = True

    suggestions_raw = data.get("suggestions") or []
    risks_raw = data.get("risks") or []
    if not isinstance(suggestions_raw, list) or not isinstance(risks_raw, list):
        return None
    suggestions = _filter_bullets([str(s) for s in suggestions_raw], allowed, stance=stance)
    risks = _filter_bullets([str(r) for r in risks_raw], allowed)
    if not suggestions:
        return None
    if forced_wait:
        risks = [
            "Signals conflict with rule majority — waiting for clearer agreement.",
            *risks,
        ][:3]

    refs = _normalize_evidence_refs(data.get("evidence_refs"), snapshot)

    return MarketBrief(
        headline=headline[:240],
        market_status=status[:1200],
        stance=stance,
        suggestions=suggestions[:3],
        risks=risks[:3] or ["Not financial advice — verify against live whale book."],
        evidence_refs=refs,
        as_of=_utcnow(),
        provider=provider,
        source="llm",
        snapshot_hash=str(snapshot.get("snapshot_hash") or ""),
    )


BRIEF_SYSTEM_PROMPT = """You are a Hyperliquid desk commentator for retail traders.
Write a Market Brief from the JSON snapshot ONLY. Respond with JSON only:
{"headline","market_status","stance","suggestions","risks","evidence_refs"}

## Stance enum (exact)
prefer_long | prefer_short | wait

## Retail copy (required)
- Prefer longs / Prefer shorts / Wait
- Forbidden: buy bias, sell bias, shorting, longing, entry points, bullish/bearish signals as advice

## How to read each snapshot field
- top3_consensus: tracked-whale long/short $ share inside HL volume Top3 (usually BTC/ETH/SOL or HYPE). Funding is NOT included here. mood from long_pct: >=58 BULLISH, <=42 BEARISH, else NEUTRAL (= balanced / no clear lean). Use per_asset for coin-level book.
- book_wide: whole tracked whale book (broader than Top3). Use as context; Top3 + coin_stances lead the call.
- coin_stances: rule votes (whale book + funding + liq). Already prefer_long/prefer_short/wait. Do not contradict a clear 2+ coin majority unless Top3 conflicts — then stance=wait.
- top3_funding: funding % for Top3 always. Flat/near-zero = no funding edge. Only treat as crowded when is_extreme=true (or listed in extreme_funding).
- extreme_funding: Top20 volume ∩ |funding| extreme. Empty list means no extreme funding — do NOT invent crowdedness.
- liq_1h / liq_24h: recent liquidation USD. Heavy long_usd flush = near-term long flush / sell-side pressure from forced longs; heavy short_usd the opposite. Small totals = weak signal.
- biggest_positions: illustrative large tracked positions — color, not a market forecast.
- coverage: positioned/tracked sample size. Low positioned → lean wait / mention thin sample in risks.

## Field roles (do not blur)
- headline: state + action. Optional semicolon form: "Top3 short-heavy; funding still flat — Prefer shorts"
- market_status: inventory / tape report ONLY — not advice. No Prefer/Monitor/Consider here.
- suggestions: what to do next (aligned with stance)
- risks: what can invalidate the read

## market_status style (CMC desk / positioning notes)
Each sentence: snapshot number (or %) + short interpretation clause.
Allowed verbs/phrases: remains, continues, signaling, suggests, tends to read as,
near-term sell pressure / buy-side pressure, inventory on the book, readily available
short/long inventory, positioning not a single catalyst, slightly nudging the balance,
what matters is …, without a structural change.
Use "N% (short-heavy|long-heavy|balanced)" labels next to shares when helpful.
Do NOT invent exchange reserves, ETF flows, RSI, price targets, burns, or news.

## Wording (avoid ambiguity)
- Never use "mixed" for market mood, Top3 book, or a coin (conflicts with Strategy tag Mixed — not in this snapshot).
- Prefer: balanced, no clear lean, split, short-heavy, long-heavy, Prefer longs vs Prefer shorts, Wait.
- headline: Top3 lean + Prefer longs/Prefer shorts/Wait. NEUTRAL → "balanced" or name the coin conflict.
- market_status: 2–4 sentences; never a lone adjective like "Bearish".
- suggestions: 1–3 actions aligned with stance. wait → watch/size-down only. prefer_short → no long suggestions (put opposing coins in risks). prefer_long → no short suggestions.
- risks: 1–3 snapshot-specific. No generic "volatility may increase".
- evidence_refs: ONLY keys from: top3_consensus, book_wide, coin_stances, top3_funding, extreme_funding, liq_1h, liq_24h, biggest_positions, coverage.
- Do NOT invent tickers, prices, or dollar amounts absent from the snapshot.
"""

BRIEF_FEW_SHOT_USER = {
    "top3_consensus": {
        "assets": ["BTC", "ETH", "SOL"],
        "per_asset": [
            {"asset": "BTC", "long_pct": 38.0, "short_pct": 62.0, "long_usd": 40e6, "short_usd": 65e6, "positioned": 20},
            {"asset": "ETH", "long_pct": 44.0, "short_pct": 56.0, "long_usd": 30e6, "short_usd": 38e6, "positioned": 18},
            {"asset": "SOL", "long_pct": 41.0, "short_pct": 59.0, "long_usd": 12e6, "short_usd": 17e6, "positioned": 12},
        ],
        "mood": "BEARISH",
        "long_pct": 40.0,
        "short_pct": 60.0,
        "reason": "Top3 by volume (BTC/ETH/SOL): Whales 60% short / 40% long (-$38M net)",
    },
    "book_wide": {
        "long_pct": 42.0,
        "short_pct": 58.0,
        "net_bias": "short",
        "positioned": 55,
        "tracked": 100,
    },
    "coin_stances": [
        {"asset": "ETH", "stance": "prefer_short", "signals": ["Whale L/S: 44/56", "Funding: flat"], "confidence": 72},
        {"asset": "BTC", "stance": "prefer_short", "signals": ["Whale L/S: 38/62", "Liq 24h: long-heavy"], "confidence": 70},
    ],
    "top3_funding": [
        {"asset": "BTC", "funding_pct": 0.005, "is_extreme": False, "note": "longs pay shorts (longs crowded when extreme+)"},
        {"asset": "ETH", "funding_pct": -0.004, "is_extreme": False, "note": "shorts pay longs (shorts crowded when extreme-)"},
        {"asset": "SOL", "funding_pct": 0.012, "is_extreme": False, "note": "longs pay shorts (longs crowded when extreme+)"},
    ],
    "extreme_funding": [],
    "liq_1h": {"long_usd": 2.1e6, "short_usd": 0.4e6, "total_usd": 2.5e6, "events": 40},
    "liq_24h": {"long_usd": 18e6, "short_usd": 9e6, "total_usd": 27e6, "events": 200},
    "biggest_positions": [{"asset": "BTC", "side": "short", "size_usd": 12e6, "alias": "whale_a"}],
    "coverage": {"positioned": 55, "tracked": 100},
    "snapshot_hash": "demo1",
}

BRIEF_FEW_SHOT_ASSISTANT = {
    "headline": "Top3 (BTC/ETH/SOL) short-heavy; funding still flat — Prefer shorts",
    "market_status": (
        "Top3 whale book remains 60% short / 40% long (~$38M net short), signaling near-term "
        "sell-side pressure from tracked-whale inventory. "
        "ETH and BTC both sit short-heavy on the book (44/56 and 38/62); what matters is that lean, "
        "not a crowded-funding story — Top3 funding stays near flat. "
        "Last 1h liquidations skew long ($2.1M vs $0.4M short), which tends to read as a long flush "
        "nudging downside pressure without a structural change."
    ),
    "stance": "prefer_short",
    "suggestions": [
        "Prefer shorts on BTC/ETH while Top3 whale book stays short-heavy.",
        "Size off the ETH Prefer shorts evidence card; keep size modest while funding stays flat.",
        "Treat SOL as follow-through only — Top3 short lean, not a solo call.",
    ],
    "risks": [
        "Funding is not extreme — a quick long squeeze can still hurt shorts.",
        "Coverage is 55/100 positioned whales; thin updates can flip the read.",
        "If coin_stances split later, drop to Wait instead of adding size.",
    ],
    "evidence_refs": ["top3_consensus", "coin_stances", "liq_1h", "top3_funding", "coverage"],
}

BRIEF_FEW_SHOT_WAIT_USER = {
    "top3_consensus": {
        "assets": ["BTC", "ETH", "HYPE"],
        "per_asset": [
            {"asset": "BTC", "long_pct": 52.0, "short_pct": 48.0, "long_usd": 50e6, "short_usd": 46e6, "positioned": 22},
            {"asset": "ETH", "long_pct": 48.0, "short_pct": 52.0, "long_usd": 33e6, "short_usd": 36e6, "positioned": 19},
            {"asset": "HYPE", "long_pct": 66.0, "short_pct": 34.0, "long_usd": 20e6, "short_usd": 10e6, "positioned": 15},
        ],
        "mood": "NEUTRAL",
        "long_pct": 54.0,
        "short_pct": 46.0,
        "reason": "Top3 by volume (BTC/ETH/HYPE): Whales roughly balanced (54% long / 46% short)",
    },
    "book_wide": {"long_pct": 51.0, "short_pct": 49.0, "net_bias": "long", "positioned": 48, "tracked": 100},
    "coin_stances": [
        {"asset": "HYPE", "stance": "prefer_long", "signals": ["Whale L/S: 66/34"], "confidence": 74},
        {"asset": "ETH", "stance": "prefer_short", "signals": ["Whale L/S: 48/52", "Liq 24h split"], "confidence": 61},
    ],
    "top3_funding": [
        {"asset": "BTC", "funding_pct": 0.001, "is_extreme": False, "note": "longs pay shorts (longs crowded when extreme+)"},
        {"asset": "ETH", "funding_pct": 0.002, "is_extreme": False, "note": "longs pay shorts (longs crowded when extreme+)"},
        {"asset": "HYPE", "funding_pct": -0.003, "is_extreme": False, "note": "shorts pay longs (shorts crowded when extreme-)"},
    ],
    "extreme_funding": [],
    "liq_1h": {"long_usd": 0.2e6, "short_usd": 0.25e6, "total_usd": 0.45e6, "events": 12},
    "liq_24h": {"long_usd": 5e6, "short_usd": 5.2e6, "total_usd": 10.2e6, "events": 90},
    "biggest_positions": [],
    "coverage": {"positioned": 48, "tracked": 100},
    "snapshot_hash": "demo2",
}

BRIEF_FEW_SHOT_WAIT_ASSISTANT = {
    "headline": "Top3 balanced; HYPE long-heavy vs ETH short-heavy — Wait",
    "market_status": (
        "Top3 whale book remains roughly balanced at 54% long / 46% short (balanced), "
        "driven by positioning split across coins rather than a single catalyst. "
        "HYPE sits long-heavy (66/34) while ETH leans short (48/52), so the book is slightly "
        "nudging both ways with no clean lean. "
        "What matters is the disagreement: Top3 funding stays flat and 1h liquidations are small "
        "(~$0.45M), so there is no extreme squeeze pressure and no structural change yet."
    ),
    "stance": "wait",
    "suggestions": [
        "Wait for Top3 whale lean or coin_stances to agree before sizing up.",
        "Watch whether HYPE long-heavy book fades or ETH short lean spreads to BTC.",
        "Keep risk light until extreme_funding or a clearer liq skew shows up.",
    ],
    "risks": [
        "Conflicting coin_stances — chasing either side is easy to reverse.",
        "Balanced Top3 mood can flip quickly on a few large whale fills.",
        "No extreme funding; do not invent a crowded long/short story.",
    ],
    "evidence_refs": ["top3_consensus", "coin_stances", "top3_funding", "liq_1h", "coverage"],
}


async def _llm_market_brief(snapshot: dict[str, Any]) -> MarketBrief | None:
    from app.services.inference import _resolve_provider

    provider = _resolve_provider()
    if provider == "heuristic":
        return None
    if provider == "openai":
        api_key = settings.openai_api_key
        base_url = settings.openai_base_url
        model = settings.openai_model
    elif provider == "deepseek":
        api_key = settings.deepseek_api_key
        base_url = settings.deepseek_base_url
        model = settings.deepseek_model
    else:
        return None
    if not api_key:
        return None

    user_payload = {k: v for k, v in snapshot.items() if k != "as_of"}
    messages = [
        {"role": "system", "content": BRIEF_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(BRIEF_FEW_SHOT_USER, default=str)},
        {"role": "assistant", "content": json.dumps(BRIEF_FEW_SHOT_ASSISTANT)},
        {"role": "user", "content": json.dumps(BRIEF_FEW_SHOT_WAIT_USER, default=str)},
        {"role": "assistant", "content": json.dumps(BRIEF_FEW_SHOT_WAIT_ASSISTANT)},
        {
            "role": "user",
            "content": "Live snapshot follows. Write the Market Brief JSON now.\n"
            + json.dumps(user_payload, default=str),
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0.15,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return _validate_brief(data, snapshot, provider)
    except Exception as exc:
        logger.warning("Market brief LLM failed (%s): %s", provider, exc)
        return None


def _should_refresh(snapshot: dict[str, Any]) -> bool:
    current = store.market_brief
    if current is None:
        return True
    new_hash = str(snapshot.get("snapshot_hash") or "")
    if new_hash and new_hash != (current.snapshot_hash or ""):
        return True
    as_of = current.as_of
    if isinstance(as_of, datetime) and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    try:
        return (_utcnow() - as_of) >= BRIEF_COOLDOWN
    except TypeError:
        return True


def persist_market_brief(brief: MarketBrief) -> None:
    db = SessionLocal()
    try:
        row = db.get(MarketBriefRow, "latest")
        if row is None:
            row = MarketBriefRow(id="latest")
            db.add(row)
        row.headline = brief.headline
        row.market_status = brief.market_status
        row.stance = brief.stance.value
        row.suggestions = json.dumps(brief.suggestions)
        row.risks = json.dumps(brief.risks)
        row.evidence_refs = json.dumps(brief.evidence_refs)
        row.provider = brief.provider
        row.source = brief.source
        row.snapshot_hash = brief.snapshot_hash
        row.as_of = brief.as_of
        row.created_at = _utcnow()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("persist market brief failed")
    finally:
        db.close()


def load_market_brief_from_db() -> MarketBrief | None:
    db = SessionLocal()
    try:
        row = db.get(MarketBriefRow, "latest")
        if row is None or not row.headline:
            return None
        return MarketBrief(
            headline=row.headline,
            market_status=row.market_status,
            stance=_parse_stance(row.stance),
            suggestions=json.loads(row.suggestions or "[]"),
            risks=json.loads(row.risks or "[]"),
            evidence_refs=json.loads(row.evidence_refs or "[]"),
            as_of=row.as_of,
            provider=row.provider,
            source=row.source,
            snapshot_hash=row.snapshot_hash or "",
        )
    except Exception:
        logger.exception("load market brief failed")
        return None
    finally:
        db.close()


async def generate_market_brief(*, force: bool = False) -> MarketBrief:
    """Build snapshot, optionally call LLM, always return a displayable brief."""
    snapshot = build_market_brief_snapshot()
    if not force and not _should_refresh(snapshot) and store.market_brief is not None:
        return store.market_brief

    brief = await _llm_market_brief(snapshot)
    if brief is None:
        brief = build_template_brief(snapshot)

    with store._lock:
        store.market_brief = brief
    persist_market_brief(brief)
    return brief
