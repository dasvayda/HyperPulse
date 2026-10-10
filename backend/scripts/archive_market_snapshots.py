"""Opt-in, lossless cold archive. Defaults to a read-only seven-day preview."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3


def archive_snapshots(source: Path, archive: Path, cutoff: str, *, apply: bool = False,
                      batch_size: int = 1000) -> dict[str, int]:
    source, archive = source.resolve(), archive.resolve()
    if source == archive or batch_size < 1:
        raise ValueError("Separate archive path and positive batch size required")
    conn = sqlite3.connect(source.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True, timeout=5)
    try:
        # Keep the latest observation of every asset, even if trading stopped.
        assets = [r[0] for r in conn.execute("SELECT DISTINCT asset FROM market_snapshots")]
        protected = [conn.execute(
            "SELECT id FROM market_snapshots WHERE asset=? ORDER BY timestamp DESC,id DESC LIMIT 1",
            (asset,),
        ).fetchone()[0] for asset in assets]
        placeholders = ",".join("?" for _ in protected) or "NULL"
        predicate = f"timestamp < ? AND id NOT IN ({placeholders})"
        args = [cutoff, *protected]
        eligible = conn.execute(f"SELECT count(*) FROM market_snapshots WHERE {predicate}", args).fetchone()[0]
        if not apply:
            return {"eligible": eligible, "archived": 0}
        conn.execute("ATTACH DATABASE ? AS cold", (str(archive),))
        conn.execute("CREATE TABLE IF NOT EXISTS cold.archive_source (path TEXT PRIMARY KEY)")
        owner = conn.execute("SELECT path FROM cold.archive_source").fetchone()
        if owner and owner[0] != str(source):
            raise ValueError("Archive belongs to another source database")
        conn.execute("INSERT OR IGNORE INTO cold.archive_source VALUES (?)", (str(source),))
        conn.execute("CREATE TABLE IF NOT EXISTS cold.market_snapshots AS SELECT * FROM main.market_snapshots WHERE 0")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS cold.snapshot_id ON market_snapshots(id)")
        conn.commit()
        columns = [r[1] for r in conn.execute("PRAGMA main.table_info(market_snapshots)")]
        equality = " AND ".join(f'a."{col}" IS s."{col}"' for col in columns)
        moved = 0
        while True:
            ids = [r[0] for r in conn.execute(f"SELECT id FROM main.market_snapshots WHERE {predicate} LIMIT ?", [*args, batch_size])]
            if not ids:
                break
            marks = ",".join("?" for _ in ids)
            conn.execute(f"INSERT OR IGNORE INTO cold.market_snapshots SELECT * FROM main.market_snapshots WHERE id IN ({marks})", ids)
            # Commit the copy first: a crash can leave duplicates, never missing history.
            conn.commit()
            conn.execute("BEGIN IMMEDIATE")
            verified = conn.execute(f"SELECT count(*) FROM main.market_snapshots s JOIN cold.market_snapshots a ON a.id=s.id WHERE s.id IN ({marks}) AND {equality}", ids).fetchone()[0]
            if verified != len(ids):
                raise ValueError("Archive verification failed; source rows preserved")
            conn.execute(f"DELETE FROM main.market_snapshots WHERE id IN ({marks})", ids)
            conn.commit()
            moved += len(ids)
        return {"eligible": eligible, "archived": moved}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("hyperpulse.db"))
    parser.add_argument("--archive", type=Path, default=Path("market-history.db"))
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.days < 7:
        parser.error("Keep at least seven days for Pulse and Paper Portfolio lookbacks")
    if args.apply:
        if args.backup is None or args.backup.exists():
            parser.error("--apply requires a new --backup path; stop the backend first")
        with sqlite3.connect(args.source.resolve().as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(args.backup) as backup:
                source.backup(backup)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).replace(tzinfo=None).isoformat(sep=" ")
    print(archive_snapshots(args.source, args.archive, cutoff, apply=args.apply))


if __name__ == "__main__":
    main()
