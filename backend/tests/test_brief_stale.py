from datetime import timedelta

from app.services.brief_report import snapshot_stale
from tests.conftest import NOW, sample_snapshot


def test_fresh_snapshot_is_not_stale():
    assert snapshot_stale(sample_snapshot(), now=NOW) is False


def test_old_book_is_stale():
    old = (NOW - timedelta(hours=2)).isoformat()
    snap = sample_snapshot(book_updated_at=old, tape_updated_at=old)
    snap["tape"]["BTC"]["updated_at"] = old
    snap["tape"]["ETH"]["updated_at"] = old
    snap["tape"]["HYPE"]["updated_at"] = old
    assert snapshot_stale(snap, now=NOW) is True
