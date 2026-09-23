"""Market Brief Telegram is two morning desk slots, not a live ticker."""

from datetime import datetime, timezone

from app.models.schemas import BriefDigest
from app.services.brief_schedule import (
    brief_coverage_empty,
    current_brief_slot,
    due_market_brief_slot,
)


def _brief(*, coverage: str = "Coverage: 57/100 (Medium)", headline: str = "Top3 lean short"):
    return type(
        "Brief",
        (),
        {
            "headline": headline,
            "digest": BriefDigest(
                as_of_line="As of 2026-09-23 | BTC $86,224 (-0.3% vs prev day)",
                funding_line="Funding (1h) +0.0013%",
                positioning=["Tracked book: 16% long / 84% short", coverage],
                read="Book stays short-heavy.",
                note="supports short bias, not confirmation",
                coverage_band="Medium",
            ),
        },
    )()


def test_asia_slot_at_kst_0905():
    now = datetime(2026, 9, 23, 0, 5, tzinfo=timezone.utc)  # 09:05 KST
    slot = current_brief_slot(now)
    assert slot is not None
    assert slot.key == "asia"
    assert slot.slot_id == "2026-09-23:asia"
    assert "09:00" in slot.label
    assert "KST" in slot.label or "Korea" in slot.label


def test_us_slot_at_et_0905_summer():
    now = datetime(2026, 9, 23, 13, 5, tzinfo=timezone.utc)  # 09:05 EDT
    slot = current_brief_slot(now)
    assert slot is not None
    assert slot.key == "us"
    assert slot.slot_id == "2026-09-23:us"


def test_us_slot_follows_winter_est():
    now = datetime(2026, 1, 15, 14, 5, tzinfo=timezone.utc)  # 09:05 EST
    slot = current_brief_slot(now)
    assert slot is not None
    assert slot.key == "us"
    assert slot.slot_id == "2026-01-15:us"


def test_kst_2100_is_not_a_slot():
    # User's 12h alternative (21:00 KST) — we skip on purpose.
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    assert current_brief_slot(now) is None


def test_outside_90_minute_window():
    now = datetime(2026, 9, 23, 1, 40, tzinfo=timezone.utc)  # 10:40 KST
    assert current_brief_slot(now) is None


def test_due_once_per_slot():
    now = datetime(2026, 9, 23, 0, 10, tzinfo=timezone.utc)
    brief = _brief()
    first = due_market_brief_slot(now=now, last_slot_id=None, brief=brief)
    assert first is not None
    again = due_market_brief_slot(now=now, last_slot_id=first.slot_id, brief=brief)
    assert again is None


def test_empty_book_waits_inside_window():
    now = datetime(2026, 9, 23, 0, 10, tzinfo=timezone.utc)
    empty = _brief(
        coverage="Coverage: 0/100 (Low)",
        headline="Tracked whale coverage still building",
    )
    assert brief_coverage_empty(empty) is True
    assert due_market_brief_slot(now=now, last_slot_id=None, brief=empty) is None
    filled = _brief()
    assert due_market_brief_slot(now=now, last_slot_id=None, brief=filled) is not None
