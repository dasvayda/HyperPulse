"""Bounded live, non-sending whale observation. Run from backend/."""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from time import monotonic


async def observe(args, log):
    from app.collectors.whales import collect_whale_events
    from app.config import settings
    from app.db import init_db
    from app.models.schemas import TraderProfile
    from app.services.alerts import classify_position_alert
    from app.services.store import store
    from app.services.whale_alert_selection import select_position_pushes

    with sqlite3.connect(args.roster.resolve().as_uri() + "?mode=ro", uri=True) as db:
        roster = db.execute(
            "SELECT address, account_value_usd FROM traders ORDER BY rank, address LIMIT ?", (args.wallets,)
        ).fetchall()
    roster = [(a, value) for a, value in roster if len(a) == 42 and a.startswith("0x")
              and all(c in "0123456789abcdefABCDEF" for c in a[2:])]
    if not roster:
        raise RuntimeError("No tracked wallet addresses found")
    init_db()
    store.traders = [
        TraderProfile(address=a, alias=a[:6] + "…" + a[-4:], rank=i,
                      account_value_usd=value or 0, pnl_usd=0, pnl_change_pct=0, win_rate=0, avg_hold_hours=0,
                      total_trades=0, preferred_assets=[], strategy_tags=[], risk_score=0, sparkline=[])
        for i, (a, value) in enumerate(roster, 1)
    ]

    def write(kind, **data):
        log.write(json.dumps({"kind": kind, "at": datetime.now(timezone.utc).isoformat(), **data}) + "\n")
        log.flush()

    write("start", wallets=len(roster), interval=args.interval, hours=args.hours,
          min_size=settings.alert_min_size_usd, fills_budget=settings.alert_execution_lookups_per_cycle)
    deadline = monotonic() + args.hours * 3600
    seen = set()
    selected = set()
    while monotonic() < deadline:
        started = monotonic()
        try:
            alerts = await collect_whale_events()
            now = datetime.now(timezone.utc)
            current = [a for a in alerts if a.timestamp >= now - timedelta(minutes=15)]
            for alert in current:
                if alert.id not in seen:
                    seen.add(alert.id)
                    write("candidate", reference_class=classify_position_alert(alert),
                          alert=alert.model_dump(mode="json"))
            audit = {}
            for alert in select_position_pushes(current, now=now, min_size=settings.alert_min_size_usd, audit=audit):
                if alert.id not in selected:
                    selected.add(alert.id)
                    write("selection", id=alert.id, members=alert.grouped_event_ids or [alert.id],
                          context_event_id=alert.prior_reduction.event_id if alert.prior_reduction else None,
                          delay_seconds=(now - alert.timestamp).total_seconds())
            coverage = store.collectors.get("whales")
            write("cycle", coverage=coverage.model_dump(mode="json") if coverage else None, decisions=audit)
        except Exception as exc:
            write("cycle_failed", error=type(exc).__name__)
        await asyncio.sleep(max(0, min(args.interval - (monotonic() - started), deadline - monotonic())))
    write("finished")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=int, choices=range(1, 25), default=24)
    parser.add_argument("--interval", type=int, choices=(60, 120, 180), default=120)
    parser.add_argument("--wallets", type=int, choices=range(1, 101), default=100)
    args = parser.parse_args()
    output = args.output.resolve()
    scratch = output.with_suffix(".db")
    if scratch.exists() or scratch == args.roster.resolve():
        parser.error("Scratch database must be new and distinct from the roster")
    if output.suffix != ".jsonl":
        parser.error("Output must end in .jsonl")
    os.environ.update(
        DATABASE_URL=f"sqlite:///{scratch.as_posix()}", ALERTS_ENABLED="false",
        TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="", USE_MOCK_DATA="false",
        CACHE_BACKEND="memory", OPENAI_API_KEY="", DEEPSEEK_API_KEY="",
        AI_PROVIDER="heuristic", TRACKED_TRADER_LIMIT=str(args.wallets),
        HYPERLIQUID_API_URL="https://api.hyperliquid.xyz",
    )
    with output.open("x", encoding="utf-8") as log:
        asyncio.run(observe(args, log))


if __name__ == "__main__":
    main()
