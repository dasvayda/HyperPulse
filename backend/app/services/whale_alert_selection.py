"""Telegram relevance policy; raw observations remain in the web Whale Alerts."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import isclose

from app.models.schemas import AlertExecutionEvidence, WhaleAlert

WINDOW_SECONDS = 300
MIN_RELATIVE_CHANGE = 0.10
ABSOLUTE_OVERRIDE_USD = 2_000_000
STRUCTURAL = {"flip", "entry", "close"}


def _instant(alert: WhaleAlert) -> datetime:
    value = alert.timestamp
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _execution(rows: list[WhaleAlert]) -> AlertExecutionEvidence | None:
    if len(rows) == 1:
        return rows[0].execution
    hashes: set[str] = set()
    executions = []
    for row in rows:
        execution = row.execution
        if not execution or not execution.verified or not execution.tx_hashes:
            return None
        keys = {key.lower() for key in execution.tx_hashes}
        # A hash can contain multiple fills. We cannot safely allocate the
        # overlap from summary-level evidence, so never add overlapping totals.
        if hashes & keys:
            return None
        hashes.update(keys)
        executions.append(execution)
    lows = [e.price_low for e in executions if e.price_low is not None]
    highs = [e.price_high or e.price_low for e in executions if e.price_high or e.price_low]
    return AlertExecutionEvidence(
        verified=True, fill_count=sum(e.fill_count for e in executions),
        notional_usd=sum(e.notional_usd for e in executions), quantity=sum(e.quantity for e in executions),
        price_low=min(lows) if len(lows) == len(rows) else None,
        price_high=max(highs) if len(highs) == len(rows) else None, tx_hashes=sorted(hashes),
    )


def select_position_pushes(alerts: list[WhaleAlert], *, now: datetime, min_size: float) -> list[WhaleAlert]:
    """Prioritize structural events; batch completed same-side quantity changes."""
    unique = {a.id: a for a in alerts if now - timedelta(minutes=15) <= _instant(a) <= now}
    groups: dict[tuple, list[WhaleAlert]] = {}
    instant = []
    for alert in sorted(unique.values(), key=lambda a: (_instant(a), a.id)):
        key = (alert.trader_address.lower(), alert.asset.upper())
        rows = groups.setdefault(key, [])
        rows.append(alert)
        if alert.position_change in STRUCTURAL and abs(alert.size_delta_usd or 0) >= min_size:
            instant.append(alert)
    selected = list(instant)
    for key, rows in groups.items():
        # At most one recent routine edition for a wallet/asset. A newer
        # structural/opposite observation supersedes the older routine batch.
        for index in range(len(rows) - 1, -1, -1):
            latest = rows[index]
            action = latest.position_change
            if action not in {"increase", "reduce"}:
                break
            bucket = int(_instant(latest).timestamp()) // WINDOW_SECONDS
            if bucket == int(now.timestamp()) // WINDOW_SECONDS:
                continue
            tail = rows[index + 1:]
            if any(a.side != latest.side or a.position_change != action for a in tail):
                break
            batch = [latest]
            for row in reversed(rows[:index]):
                if (int(_instant(row).timestamp()) // WINDOW_SECONDS != bucket or
                        row.side != latest.side or row.position_change != action):
                    break
                batch.insert(0, row)
            before, after = batch[0].previous_quantity, latest.current_quantity
            if any(
                left.current_quantity is None or right.previous_quantity is None
                or not isclose(left.current_quantity, right.previous_quantity, rel_tol=1e-9)
                for left, right in zip(batch, batch[1:])
            ):
                break
            execution = _execution(batch)
            if before is None or after is None or before <= 0 or after <= 0 or not execution or not execution.verified:
                break
            change = after - before
            if (change > 0) != (action == "increase") or not change:
                break
            delta = change * latest.size_usd / after
            if abs(delta) < min_size or (abs(change) / before < MIN_RELATIVE_CHANGE and abs(delta) < ABSOLUTE_OVERRIDE_USD):
                break
            batch_id = sha256(repr((key, latest.side.value, bucket)).encode()).hexdigest()[:32]
            selected.append(latest.model_copy(update={
                "id": f"batch-{batch_id}", "execution": execution,
                "size_delta_usd": delta, "previous_quantity": before,
                "grouped_event_ids": [row.id for row in batch], "trigger_floor_usd": min_size,
            }))
            break
    selected.sort(key=lambda a: ({"flip": 0, "entry": 1, "close": 1}.get(a.position_change, 2),
                                 -abs(a.size_delta_usd or 0), a.id))
    return selected
