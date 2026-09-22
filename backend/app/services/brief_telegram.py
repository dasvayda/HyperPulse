"""Telegram formatting for Market Brief (BL-14 desk copy → outbound)."""

from __future__ import annotations

import hashlib
import re

from app.models.schemas import BriefStance, MarketBrief

_STANCE_BADGE = {
    BriefStance.PREFER_LONG: "LONG lean",
    BriefStance.PREFER_SHORT: "SHORT lean",
    BriefStance.WAIT: "WAIT",
}


def stance_badge(stance: BriefStance | str) -> str:
    if isinstance(stance, BriefStance):
        return _STANCE_BADGE.get(stance, "WAIT")
    try:
        return _STANCE_BADGE.get(BriefStance(stance), "WAIT")
    except ValueError:
        return "WAIT"


def brief_send_key(brief: MarketBrief) -> str:
    """Stable id for Telegram dedupe (prefer snapshot_hash)."""
    snap = (brief.snapshot_hash or "").strip()
    if snap:
        return snap
    tldr = brief.tldr
    stance = brief.stance.value if hasattr(brief.stance, "value") else str(brief.stance)
    raw = "|".join(
        [
            brief.headline or "",
            (tldr.now if tldr else "") or "",
            (tldr.short_read if tldr else "") or "",
            (tldr.however if tldr else "") or "",
            stance,
            (brief.market_status or "")[:160],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _desk_blurb(market_status: str, *, max_sentences: int = 3, max_chars: int = 480) -> str:
    """Take the first few sentences of market_status as desk-tone prose."""
    text = (market_status or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    if not parts:
        return text[:max_chars]
    blurb = " ".join(parts[:max_sentences])
    if len(blurb) > max_chars:
        blurb = blurb[: max_chars - 1].rstrip() + "…"
    return blurb


def format_market_brief_telegram(brief: MarketBrief) -> tuple[str, list[str]]:
    """Build title + HTML lines. TL;DR stays descriptive; Prefer stays on Stance line."""
    scope = (brief.asset or "Top3").upper() if brief.asset else "Top3"
    title = f"MARKET BRIEF · {scope}"
    if brief.stale:
        title = f"MARKET BRIEF · STALE · {scope}"

    lines: list[str] = [f"<b>{title}</b>"]
    tldr = brief.tldr
    if tldr is not None:
        for slot in (tldr.now, tldr.short_read, tldr.however):
            bit = (slot or "").strip()
            if bit:
                lines.append(f"• {bit}")

    desk = _desk_blurb(brief.market_status)
    if desk:
        lines.append("")
        lines.append(desk)

    lines.append(f"Stance · {stance_badge(brief.stance)}")

    if brief.suggestions:
        note = str(brief.suggestions[0] or "").strip()
        if note:
            # One optional note — keep short; Prefer belongs on Stance, not buried here.
            if len(note) > 180:
                note = note[:179].rstrip() + "…"
            lines.append(f"Note · {note}")

    return title, lines
