from app.services.brief_report import build_tldr_slots, tldr_has_prefer
from tests.conftest import sample_snapshot


def test_tldr_three_slots_have_numbers_and_tracked():
    tldr = build_tldr_slots(sample_snapshot())
    assert tldr.now
    assert tldr.short_read
    assert tldr.however
    assert "vs prev day" in tldr.now
    assert "funding" in tldr.now.lower()
    assert "tracked" in tldr.short_read.lower()
    assert "$" in tldr.short_read
    assert "coverage" in tldr.however.lower() or "tracked" in tldr.however.lower()
    assert not tldr_has_prefer(tldr)


def test_tldr_slot3_never_empty():
    tldr = build_tldr_slots(sample_snapshot())
    assert len(tldr.however.strip()) > 10
