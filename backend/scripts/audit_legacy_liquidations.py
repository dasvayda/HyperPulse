"""Read-only audit of a SQLite DB copy. Never upgrades legacy events to verified."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def audit(path: Path) -> dict:
    path = path.resolve(strict=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        rows = db.execute("SELECT date(timestamp), asset, count(*), sum(size_usd), "
                          "sum(CASE WHEN tx_hash IS NOT NULL AND tx_hash != '' THEN 1 ELSE 0 END) "
                          "FROM liquidations GROUP BY date(timestamp), asset ORDER BY date(timestamp), asset").fetchall()
        return {"classification": "legacy_unverified", "verified": False,
                "reason": "Legacy schema has no liquidation marker, wallet attribution or raw source payload; hash alone is insufficient",
                "groups": [{"date": r[0], "asset": r[1], "events": r[2], "notional_usd": r[3], "with_tx_hash": r[4]} for r in rows]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database_copy", type=Path, help="Explicit path to a SQLite DB copy")
    args = parser.parse_args()
    print(json.dumps(audit(args.database_copy), indent=2))
