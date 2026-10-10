import sqlite3

import pytest

from scripts.archive_market_snapshots import archive_snapshots


def make_source(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE market_snapshots (id INTEGER PRIMARY KEY, asset TEXT, mark_price REAL, timestamp TEXT)")
        db.executemany("INSERT INTO market_snapshots VALUES (?,?,?,?)", [
            (1, "BTC", 100, "2026-01-01"), (2, "BTC", 120, "2026-01-09"),
            (3, "OLD", 5, "2026-01-01"), (4, "BTC", 110, "2026-01-02"),
        ])


def count(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0]


def test_preview_does_not_create_archive_or_delete(tmp_path):
    source, archive = tmp_path / "source.db", tmp_path / "cold.db"
    make_source(source)
    assert archive_snapshots(source, archive, "2026-01-03") == {"eligible": 2, "archived": 0}
    assert count(source) == 4
    assert not archive.exists()


def test_lossless_batched_archive_keeps_latest_and_is_idempotent(tmp_path):
    source, archive = tmp_path / "source.db", tmp_path / "cold.db"
    make_source(source)
    assert archive_snapshots(source, archive, "2026-01-03", apply=True, batch_size=1)["archived"] == 2
    assert count(source) == 2
    assert count(archive) == 2
    assert archive_snapshots(source, archive, "2026-01-03", apply=True)["archived"] == 0
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT id FROM market_snapshots ORDER BY id").fetchall() == [(2,), (3,)]


def test_archive_conflict_does_not_delete_source(tmp_path):
    source, archive = tmp_path / "source.db", tmp_path / "cold.db"
    make_source(source)
    make_source(archive)
    with sqlite3.connect(archive) as db:
        db.execute("UPDATE market_snapshots SET mark_price=999 WHERE id=1")
    with pytest.raises(ValueError, match="verification"):
        archive_snapshots(source, archive, "2026-01-03", apply=True)
    assert count(source) == 4


def test_same_path_is_rejected(tmp_path):
    source = tmp_path / "source.db"
    make_source(source)
    with pytest.raises(ValueError):
        archive_snapshots(source, source, "2026-01-03", apply=True)
