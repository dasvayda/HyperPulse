"""Replay finalized observation JSONL against the current policy without sending."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from app.models.schemas import WhaleAlert
from app.services.whale_alert_selection import PositionPushPolicy


def replay(records):
    policy = PositionPushPolicy()
    pending, original, selections = [], {}, {}
    audit_counts = Counter()
    floor = 500_000
    completed = False
    for row in records:
        kind = row["kind"]
        if kind == "start":
            floor = row["min_size"]
        elif kind == "candidate":
            pending.append(WhaleAlert.model_validate(row["alert"]))
        elif kind == "selection":
            original[row["id"]] = row
        elif kind == "cycle":
            now = datetime.fromisoformat(row["at"])
            pending = [alert for alert in pending if (now - alert.timestamp).total_seconds() <= 900]
            audit = {}
            for alert in policy.select(pending, now=now, min_size=floor, audit=audit):
                selections.setdefault(alert.id, (
                    alert, (now - alert.timestamp).total_seconds(),
                ))
            audit_counts.update(set(audit.items()))
        elif kind == "finished":
            completed = True
    return {
        "completed": completed, "baseline": len(original), "new": len(selections),
        "baseline_max_seconds": max((r["delay_seconds"] for r in original.values()), default=None),
        "new_max_seconds": max((delay for _, delay in selections.values()), default=None),
        "structural": sum(a.position_change in {"entry", "close", "flip"} for a, _ in selections.values()),
        "rescued_large_reductions": sum(a.priority_reduction for a, _ in selections.values()),
        "observed_decisions": dict(Counter(reason for _, reason in audit_counts)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    with parser.parse_args().log.open(encoding="utf-8") as stream:
        print(json.dumps(replay(map(json.loads, stream)), indent=2))
