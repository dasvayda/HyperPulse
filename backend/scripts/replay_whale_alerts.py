"""Read-only replay of archived Telegram position alerts, not a delivery simulator."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

from pydantic import ValidationError

from app.models.schemas import WhaleAlert
from app.services.whale_alert_selection import select_position_pushes


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def replay(rows, min_size: float, cadence: int) -> dict:
    missing = Counter()
    groups = Counter()
    available = defaultdict(list)
    verified = 0
    repeat_within_5m = 0
    prior = {}
    for payload, sent_at in rows:
        data = json.loads(payload)
        key = (data.get("trader_address", "").lower(), data.get("asset", "").upper(), data.get("side", ""))
        groups[key] += 1
        sent = utc(sent_at)
        if key in prior and sent - prior[key] <= timedelta(minutes=5):
            repeat_within_5m += 1
        prior[key] = sent
        verified += int(bool((data.get("execution") or {}).get("verified")))
        absent = [field for field in ("id", "timestamp", "position_change") if not data.get(field)]
        if data.get("position_change") not in {"entry", "close", "flip"}:
            absent += [field for field in ("previous_quantity", "current_quantity") if data.get(field) is None]
        if absent:
            missing.update(absent)
            continue
        try:
            available[key].append(WhaleAlert.model_validate(data))
        except ValidationError:
            missing["invalid_payload"] += 1
    complete = sum(map(len, available.values()))
    result = {
        "historical_sent": len(rows), "labeled_verified": verified,
        "repeat_within_5m": repeat_within_5m,
        "largest_wallet_asset_side_group": max(groups.values(), default=0),
        "replayable_records": complete, "unreplayable_records": len(rows) - complete,
        "missing_fields": dict(missing),
        "new_candidates": None, "max_selection_delay_seconds": None,
    }
    # Missing observations can change grouping or supersession. Do not turn
    # historical schema gaps into apparent suppression.
    if not complete or complete != len(rows):
        return result

    events = sorted(
        ((utc(a.timestamp.isoformat()), a.id, a) for items in available.values() for a in items),
        key=lambda event: event[:2],
    )
    start = int(events[0][0].timestamp()) // cadence * cadence
    end = int(events[-1][0].timestamp()) + 900
    seen, pending, delays = {}, [], []
    index = 0
    for tick in range(start, end + 1, cadence):
        now = datetime.fromtimestamp(tick, timezone.utc)
        while index < len(events) and events[index][0] <= now:
            pending.append(events[index][2])
            index += 1
        pending = [a for a in pending if utc(a.timestamp.isoformat()) >= now - timedelta(minutes=15)]
        for alert in select_position_pushes(pending, now=now, min_size=min_size):
            if alert.id not in seen:
                seen[alert.id] = alert
                delays.append((now - utc(alert.timestamp.isoformat())).total_seconds())
    result.update(new_candidates=len(seen), max_selection_delay_seconds=max(delays, default=None))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path)
    parser.add_argument("--day", required=True, type=date.fromisoformat, help="UTC delivery day")
    parser.add_argument("--min-size", type=float, default=500_000)
    parser.add_argument("--cadence", type=int, choices=(30, 60, 120, 300), default=120)
    args = parser.parse_args()
    with sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute(
            """SELECT payload, sent_at FROM alerts
            WHERE channel='telegram' AND status='sent' AND sent_at >= ? AND sent_at < ?
            AND (event_type GLOB 'whale_move_*' OR event_type GLOB 'big_trade_*')
            ORDER BY sent_at, id""",
            (args.day.isoformat(), (args.day + timedelta(days=1)).isoformat()),
        ).fetchall()
    print(json.dumps({"day_utc": args.day.isoformat(), "cadence_seconds": args.cadence,
                      **replay(rows, args.min_size, args.cadence)}, indent=2))


if __name__ == "__main__":
    main()
