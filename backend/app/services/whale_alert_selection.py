"""Telegram relevance policy; raw observations remain in the web Whale Alerts."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import isclose

from app.models.schemas import AlertExecutionEvidence, PriorWhaleReduction, WhaleAlert

WINDOW_SECONDS = 300
MIN_RELATIVE_CHANGE = 0.10
ABSOLUTE_OVERRIDE_USD = 2_000_000
STRUCTURAL = {"flip", "entry", "close"}
MAX_ROUTINE_AGE = timedelta(minutes=7)


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


def select_position_pushes(alerts: list[WhaleAlert], *, now: datetime, min_size: float,
                           audit: dict[str, str] | None = None,
                           policy: "PositionPushPolicy | None" = None) -> list[WhaleAlert]:
    """Prioritize structural events; batch completed same-side quantity changes."""
    unique = {a.id: a for a in alerts if now - timedelta(minutes=15) <= _instant(a) <= now}
    if audit is not None:
        audit.update((a.id, "superseded_or_unsupported" if a.id in unique else "outside_window") for a in alerts)

    def note(rows, reason):
        if audit is not None:
            audit.update((row.id, reason) for row in rows)
    groups: dict[tuple, list[WhaleAlert]] = {}
    instant = []
    for alert in sorted(unique.values(), key=lambda a: (_instant(a), a.id)):
        key = (alert.trader_address.lower(), alert.asset.upper())
        rows = groups.setdefault(key, [])
        if policy is not None and alert.position_change in {"close", "flip"}:
            note([row for row in rows if row.position_change in {"increase", "reduce"}],
                 "superseded_by_close_or_flip")
        if alert.position_change in STRUCTURAL and abs(alert.size_delta_usd or 0) >= min_size:
            prior = rows[-1] if rows else None
            # Carry the closest verified trim only when the observed quantity
            # connects to the close. It is context, not evidence of the close.
            if (alert.position_change == "close" and prior and prior.position_change == "reduce"
                    and prior.side == alert.side and prior.execution and prior.execution.verified
                    and prior.previous_quantity and prior.current_quantity and alert.previous_quantity
                    and prior.previous_quantity > prior.current_quantity > 0
                    and isclose(prior.current_quantity, alert.previous_quantity, rel_tol=1e-9)
                    and timedelta(0) < _instant(alert) - _instant(prior) <= timedelta(seconds=WINDOW_SECONDS)):
                alert = alert.model_copy(update={"prior_reduction": PriorWhaleReduction(
                    event_id=prior.id, observed_at=_instant(prior),
                    previous_quantity=prior.previous_quantity, current_quantity=prior.current_quantity,
                    execution=prior.execution,
                )})
                note([prior], "context_in_close")
            instant.append(alert)
            note([alert], "selected_structural")
        elif alert.position_change in STRUCTURAL:
            note([alert], "below_size_floor")
        rows.append(alert)
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
                note([latest], "waiting_for_bucket")
                continue
            tail = rows[index + 1:]
            if any(a.side != latest.side or a.position_change != action for a in tail):
                if policy is not None:
                    if not audit or audit.get(latest.id) != "context_in_close":
                        note([latest], "superseded_by_later_change")
                break
            batch = [latest]
            for row in reversed(rows[:index]):
                if (int(_instant(row).timestamp()) // WINDOW_SECONDS != bucket or
                        row.side != latest.side or row.position_change != action):
                    break
                batch.insert(0, row)
            window_key = (*key, latest.side.value, bucket)
            if policy is not None:
                if now - _instant(latest) > MAX_ROUTINE_AGE:
                    note(batch, "candidate_too_old")
                    break
                if window_key in policy.closed:
                    frozen, reason = policy.closed[window_key]
                    note(batch, reason)
                    if frozen is not None and now - _instant(frozen) <= MAX_ROUTINE_AGE:
                        selected.append(frozen)
                    break
                # Mark before evaluating: the bucket may not be reconsidered
                # if earlier rows later disappear or a delayed row arrives.
                policy.closed[window_key] = (None, "closed_rejected")

            def reject(reason):
                note(batch, reason)
                if policy is None:
                    return
                rescue = next((row for row in reversed(batch)
                               if row.position_change == "reduce" and row.execution
                               and row.execution.verified and row.execution.tx_hashes
                               and abs(row.size_delta_usd or 0) >= max(min_size, ABSOLUTE_OVERRIDE_USD)
                               and now - _instant(row) <= MAX_ROUTINE_AGE), None)
                # A newer trim is reflected in the position total, but never
                # counted as part of the verified execution we rescued.
                if rescue is not None:
                    candidate = rescue.model_copy(update={
                        "size_usd": latest.size_usd, "entry_price": latest.entry_price,
                        "leverage": latest.leverage, "roi_pct": latest.roi_pct,
                        "unrealized_pnl_usd": latest.unrealized_pnl_usd,
                        "position_observed_at": _instant(latest), "priority_reduction": True,
                    })
                    policy.closed[window_key] = (candidate, "verified_large_reduction")
                    note([rescue], "verified_large_reduction")
                    selected.append(candidate)
                else:
                    policy.closed[window_key] = (None, reason)

            before, after = batch[0].previous_quantity, latest.current_quantity
            if any(
                left.current_quantity is None or right.previous_quantity is None
                or not isclose(left.current_quantity, right.previous_quantity, rel_tol=1e-9)
                for left, right in zip(batch, batch[1:])
            ):
                reject("quantity_discontinuity")
                break
            execution = _execution(batch)
            if before is None or after is None or before <= 0 or after <= 0:
                reject("missing_quantity")
                break
            if not execution or not execution.verified:
                reject(("execution_hash_overlap" if all(
                    row.execution and row.execution.verified and row.execution.tx_hashes for row in batch
                ) else "unverified_execution") if policy is not None else "unverified_or_overlapping_execution")
                break
            change = after - before
            if (change > 0) != (action == "increase") or not change:
                reject("inconsistent_direction")
                break
            delta = change * latest.size_usd / after
            if abs(delta) < min_size or (abs(change) / before < MIN_RELATIVE_CHANGE and abs(delta) < ABSOLUTE_OVERRIDE_USD):
                reject("below_change_threshold")
                break
            batch_id = sha256(repr((key, latest.side.value, bucket)).encode()).hexdigest()[:32]
            selected.append(latest.model_copy(update={
                "id": f"batch-{batch_id}", "execution": execution,
                "size_delta_usd": delta, "previous_quantity": before,
                "grouped_event_ids": [row.id for row in batch], "trigger_floor_usd": min_size,
            }))
            note(batch, "selected_batch")
            if policy is not None:
                policy.closed[window_key] = (selected[-1], "selected_batch")
            break
    selected.sort(key=lambda a: ({"flip": 0, "entry": 1, "close": 1}.get(a.position_change, 2),
                                 not a.priority_reduction, -abs(a.size_delta_usd or 0), a.id))
    return selected


class PositionPushPolicy:
    """Process-local frozen decisions and routine selection cooldown."""

    def __init__(self):
        self.closed = {}
        self.recent = {}
        self.suppressed = set()

    def select(self, alerts, *, now, min_size, audit=None):
        cutoff = now.timestamp() - 15 * 60
        self.closed = {k: v for k, v in self.closed.items() if (k[-1] + 1) * WINDOW_SECONDS >= cutoff}
        self.recent = {k: v for k, v in self.recent.items() if v[0].timestamp() >= cutoff}
        self.suppressed.intersection_update(a.id for a, _ in self.closed.values() if a)
        accepted = []
        for alert in select_position_pushes(alerts, now=now, min_size=min_size, audit=audit, policy=self):
            if alert.position_change in STRUCTURAL or alert.priority_reduction:
                accepted.append(alert)
                continue
            key = (alert.trader_address.lower(), alert.asset.upper(), alert.side, alert.position_change)
            last = self.recent.get(key)
            if alert.id in self.suppressed or (last and last[1] != alert.id and now - last[0] < timedelta(seconds=WINDOW_SECONDS)):
                self.suppressed.add(alert.id)
                if audit is not None:
                    audit.update((member, "routine_cooldown") for member in alert.grouped_event_ids)
                continue
            if not last or last[1] != alert.id:
                self.recent[key] = (now, alert.id)
            accepted.append(alert)
        return accepted
