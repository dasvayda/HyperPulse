from __future__ import annotations

"""
One-off utility to remove mock/seed data from the local database.

Safe to run multiple times; it only deletes obviously fake or dev-time rows.
"""

import re

from app.db import SessionLocal
from app.models.orm import AlertRow, LiquidationRow, PositionRow, TraderRow


_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _is_real_address(address: str | None) -> bool:
    if not address:
        return False
    return bool(_ADDRESS_RE.match(address))


def main() -> None:
    db = SessionLocal()
    try:
        removed_traders = 0
        for row in db.query(TraderRow).all():
            if not _is_real_address(row.address):
                db.delete(row)
                removed_traders += 1

        # Positions and liquidations are safe to fully clear; they will be
        # repopulated by the real-time collectors.
        removed_positions = db.query(PositionRow).delete()
        removed_liqs = db.query(LiquidationRow).delete()

        # Alert history from early mock runs is also safe to drop.
        removed_alerts = db.query(AlertRow).delete()

        db.commit()
        print(
            f"Removed mock rows: traders={removed_traders}, "
            f"positions={removed_positions}, liquidations={removed_liqs}, "
            f"alerts={removed_alerts}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

