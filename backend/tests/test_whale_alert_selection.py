from datetime import datetime, timedelta, timezone

from app.models.schemas import AlertExecutionEvidence
from app.services.alerts import _delivery_dedupe_key, format_whale_move_lines
from app.services.whale_alert_selection import select_position_pushes
from tests.test_whale_move_telegram import _alert

NOW = datetime(2026, 11, 14, 10, 5, tzinfo=timezone.utc)


def move(id, minute, before, after, tx, **updates):
    return _alert(
        id=id, timestamp=NOW - timedelta(minutes=minute), position_change="increase",
        previous_quantity=before, current_quantity=after, size_usd=after * 100_000,
        size_delta_usd=(after - before) * 100_000,
        execution=AlertExecutionEvidence(verified=True, tx_hashes=[tx], fill_count=1,
                                         notional_usd=300_000, price_low=2494.1, price_high=2494.2),
    ).model_copy(update=updates)


def select(*rows, now=NOW):
    return select_position_pushes(list(rows), now=now, min_size=500_000)


def test_batches_completed_window_once_with_stable_id_and_distinct_totals():
    a, b = move("a", 4, 30, 33, "0xa"), move("b", 2, 33, 36, "0xb")
    result, = select(a, b, a)
    assert result.id == select(b, a)[0].id
    assert result.grouped_event_ids == ["a", "b"]
    assert result.execution.fill_count == 2 and result.execution.notional_usd == 600_000
    assert result.size_delta_usd == 600_000 and result.size_usd == 3_600_000
    _, lines = format_whale_move_lines(result)
    assert "Why now:" in lines[1] and "20.0%" in lines[1]
    assert any("@ $2,494" in line and "–" not in line for line in lines)
    assert select(a, b, now=NOW - timedelta(minutes=1)) == []
    payload = result.model_dump()
    assert _delivery_dedupe_key("whale_move_entry", payload) == _delivery_dedupe_key("big_trade_entry", payload)


def test_overlap_unverified_and_small_relative_changes_stay_off_telegram():
    a = move("a", 4, 30, 33, "0xa")
    assert select(a, move("b", 2, 33, 36, "0xA")) == []
    assert select(a, move("b", 2, 33, 36, "0xb", execution=None)) == []
    assert select(a, move("b", 2, 35, 39, "0xb")) == []
    assert select(move("a", 2, 100, 106, "0xa")) == []


def test_flip_bypasses_batch_delay_and_supersedes_old_routine_push():
    a = move("a", 3, 30, 36, "0xa")
    flip = move("flip", 0, 36, 15, "0xf", position_change="flip",
                size_delta_usd=1_500_000, execution=None)
    assert select(a, flip) == [flip]
