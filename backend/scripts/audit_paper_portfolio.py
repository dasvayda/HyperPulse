"""Read-only SQLite paper-ledger reconciliation; never imports the running app."""

import argparse
import json
import math
import sqlite3
from pathlib import Path


def audit(path: Path) -> dict:
    errors = []
    reports = []
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        for strategy in db.execute("SELECT * FROM paper_strategies"):
            sid = strategy["id"]
            config = json.loads(strategy["config_json"])
            trades = db.execute("SELECT * FROM paper_trades WHERE strategy_id=?", (sid,)).fetchall()
            equity = db.execute("SELECT * FROM paper_equity_snapshots WHERE strategy_id=? ORDER BY created_at", (sid,)).fetchall()

            def check(label, actual, expected):
                if not math.isfinite(actual) or not math.isclose(actual, expected, abs_tol=0.001, rel_tol=1e-8):
                    errors.append(f"{sid}: {label}: actual={actual}, expected={expected}")

            for row in trades:
                prefix = row["id"]
                check(prefix + " notional", row["notional_usd"], row["quantity"] * row["fill_price"])
                check(prefix + " fee", row["fee_usd"], row["notional_usd"] * config["taker_fee_rate"])
                check(prefix + " slippage", row["slippage_usd"], abs(row["fill_price"] - row["mark_price"]) * row["quantity"])
            check("fees", strategy["cumulative_fees"], sum(row["fee_usd"] for row in trades))
            check("slippage", strategy["cumulative_slippage"], sum(row["slippage_usd"] for row in trades))
            check("realized pnl", strategy["realized_pnl"], sum(row["realized_pnl_usd"] for row in trades))
            check("cash", strategy["cash"], strategy["initial_cash"] + strategy["realized_pnl"] - strategy["cumulative_fees"] + strategy["cumulative_funding"])
            for row in equity:
                check(row["id"] + " NAV", row["nav"], row["cash"] + row["unrealized_pnl_usd"])
            hours = len({row["bucket"] for row in equity})
            closes = sum(row["action"] == "close" for row in trades)
            reports.append({
                "strategy": sid, "observed_hour_buckets": hours,
                "observed_days_equivalent": round(hours / 24, 2),
                "fully_closed_positions": closes, "trades": len(trades),
                "first_equity_at": equity[0]["created_at"] if equity else None,
                "last_equity_at": equity[-1]["created_at"] if equity else None,
                "minimum_sample_met": hours >= 720 and closes >= 100,
                "cash": strategy["cash"], "funding_net": strategy["cumulative_funding"],
            })
    return {"strategies": reports, "errors": errors, "accounting_ok": not errors,
            "note": "Sample thresholds and accounting checks do not approve public launch. Source provenance and funding-history audit are still required."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    report = audit(args.database)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["accounting_ok"] else 1)
