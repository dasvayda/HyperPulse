"""Telegram formatting for Market Brief (labeled digest → outbound)."""

from __future__ import annotations

import hashlib

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


def brief_scope_label(brief: MarketBrief) -> str:
    if brief.asset:
        return brief.asset.upper()
    tabs = [str(a).upper() for a in (brief.tab_assets or []) if a]
    if tabs:
        return f"Top3 ({'/'.join(tabs)})"
    return "Top3"


def brief_send_key(brief: MarketBrief) -> str:
    """Stable id for Telegram dedupe (prefer snapshot_hash)."""
    snap = (brief.snapshot_hash or "").strip()
    if snap:
        return snap
    tldr = brief.tldr
    digest = brief.digest
    stance = brief.stance.value if hasattr(brief.stance, "value") else str(brief.stance)
    raw = "|".join(
        [
            brief.headline or "",
            (digest.read if digest else "") or "",
            (tldr.now if tldr else "") or "",
            (tldr.short_read if tldr else "") or "",
            (tldr.however if tldr else "") or "",
            stance,
            (brief.market_status or "")[:160],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def format_market_brief_telegram(brief: MarketBrief) -> tuple[str, list[str]]:
    """Labeled digest: tape → Positioning → Read → Stance. No prose dump."""
    scope = brief_scope_label(brief)
    title = f"MARKET BRIEF · {scope}"
    if brief.stale:
        title = f"MARKET BRIEF · STALE · {scope}"

    lines: list[str] = [f"<b>{title}</b>"]
    digest = brief.digest
    if digest is not None:
        if digest.as_of_line:
            lines.append(digest.as_of_line)
        if digest.funding_line:
            lines.append(digest.funding_line)
        lines.append("")
        lines.append("<b>Positioning</b>")
        for item in digest.positioning:
            bit = (item or "").strip()
            if bit:
                lines.append(f"• {bit}")
        if digest.read:
            lines.append("")
            lines.append("<b>Read</b>")
            lines.append(digest.read)
    else:
        tldr = brief.tldr
        if tldr is not None:
            for slot in (tldr.now, tldr.short_read, tldr.however):
                bit = (slot or "").strip()
                if bit:
                    lines.append(f"• {bit}")

    lines.append("")
    lines.append(f"Stance · {stance_badge(brief.stance)}")

    note = (digest.note if digest else "") or ""
    if not note and brief.suggestions:
        note = str(brief.suggestions[0] or "").strip()
    if note:
        if len(note) > 180:
            note = note[:179].rstrip() + "…"
        lines.append(f"Note · {note}")

    return title, lines
