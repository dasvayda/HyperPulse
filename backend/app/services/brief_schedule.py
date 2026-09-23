"""Telegram Market Brief cadence: two desk slots per day.

Insights on the website can stay live. Telegram is a desk note, so it fires
once at Asia 09:00 and once at US 09:00 — not every snapshot-hash tick.

Why not KST 09:00 + 12h (21:00)? Crypto desks actually read a morning note at
the two big sessions (Seoul / New York). 21:00 KST is late for Asia and still
early for US. 09:00 America/New_York follows DST automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ASIA_ZONE = ZoneInfo("Asia/Seoul")
US_ZONE = ZoneInfo("America/New_York")
SLOT_HOUR = 9
WINDOW = timedelta(minutes=90)

_ZONES: tuple[tuple[str, str, ZoneInfo], ...] = (
    ("asia", "Asia", ASIA_ZONE),
    ("us", "US", US_ZONE),
)


@dataclass(frozen=True)
class BriefSlot:
    slot_id: str
    key: str
    label: str


def current_brief_slot(now: datetime | None = None) -> BriefSlot | None:
    """Return the 09:00 desk slot we are inside, or None outside both windows."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)

    for key, name, zone in _ZONES:
        local = instant.astimezone(zone)
        start = local.replace(hour=SLOT_HOUR, minute=0, second=0, microsecond=0)
        elapsed = local - start
        if timedelta(0) <= elapsed < WINDOW:
            tz_label = local.tzname() or zone.key
            return BriefSlot(
                slot_id=f"{local.date().isoformat()}:{key}",
                key=key,
                label=f"{name} 09:00 {tz_label}",
            )
    return None


def brief_coverage_empty(brief: object) -> bool:
    headline = str(getattr(brief, "headline", "") or "")
    if "coverage still building" in headline.lower():
        return True
    digest = getattr(brief, "digest", None)
    if digest is None:
        return False
    for line in getattr(digest, "positioning", None) or []:
        compact = str(line or "").replace(" ", "")
        if compact.startswith("Coverage:0/"):
            return True
    return False


def due_market_brief_slot(
    *,
    now: datetime | None = None,
    last_slot_id: str | None = None,
    brief: object | None = None,
) -> BriefSlot | None:
    """Slot to publish now, or None if outside the window / already sent / empty book."""
    slot = current_brief_slot(now)
    if slot is None:
        return None
    if last_slot_id and last_slot_id == slot.slot_id:
        return None
    if brief is not None and brief_coverage_empty(brief):
        return None
    return slot
