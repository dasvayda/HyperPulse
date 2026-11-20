from datetime import datetime, timedelta, timezone

from app.models.schemas import AlertExecutionEvidence
from app.services.alerts import _delivery_dedupe_key, format_whale_move_lines
from app.services.whale_alert_selection import select_position_pushes
from app.services.whale_alert_selection import PositionPushPolicy
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


def test_audit_reports_wait_then_rejection_without_changing_selection():
    alert = move("a", 2, 30, 36, "0xa", execution=None)
    audit = {}
    later = select_position_pushes([alert], now=NOW, min_size=500_000, audit=audit)
    assert later == []
    assert audit == {"a": "unverified_or_overlapping_execution"}
    select_position_pushes([alert], now=NOW - timedelta(minutes=1), min_size=500_000, audit=audit)
    assert audit == {"a": "waiting_for_bucket"}


def test_closed_rejection_does_not_revive_when_a_member_disappears():
    policy = PositionPushPolicy()
    a = move("a", 4, 30, 36, "0xa", execution=None)
    b = move("b", 2, 36, 42, "0xb")
    assert policy.select([a, b], now=NOW, min_size=500_000) == []
    audit = {}
    assert policy.select([b], now=NOW + timedelta(minutes=2), min_size=500_000, audit=audit) == []
    assert audit["b"] == "unverified_execution"
    assert policy.select([b], now=NOW + timedelta(minutes=8), min_size=500_000) == []


def test_large_verified_trim_rescued_without_adding_unverified_execution():
    policy = PositionPushPolicy()
    trim = move("trim", 4, 100, 70, "0xa", position_change="reduce",
                size_delta_usd=-3_000_000)
    other = move("other", 2, 70, 65, "0xb", position_change="reduce", execution=None)
    result, = policy.select([trim, other], now=NOW, min_size=500_000)
    assert result.priority_reduction and result.id == trim.id
    assert result.execution == trim.execution
    assert result.size_usd == other.size_usd and result.position_observed_at == other.timestamp


def test_adjacent_routine_window_stays_suppressed_but_close_bypasses():
    policy = PositionPushPolicy()
    a = move("a", 2, 30, 36, "0xa")
    assert policy.select([a], now=NOW + timedelta(minutes=3), min_size=500_000)
    b = move("b", -3, 36, 42, "0xb")
    audit = {}
    assert policy.select([a, b], now=NOW + timedelta(minutes=5), min_size=500_000, audit=audit) == []
    assert audit["b"] == "routine_cooldown"
    close = b.model_copy(update={"id": "close", "position_change": "close"})
    assert policy.select([a, b, close], now=NOW + timedelta(minutes=6), min_size=500_000)[0].id == "close"


def test_zec_close_keeps_verified_prior_trim_without_verifying_the_close():
    trim = move("trim", 2, 7000, 3500, "0xa", asset="ZEC", position_change="reduce",
                size_delta_usd=-3096030)
    close = move("close", 0, 3500, 0, "0xb", asset="ZEC", position_change="close",
                 size_delta_usd=-3096030, execution=None, size_usd=0)
    audit = {}
    result, = select_position_pushes([trim, close], now=NOW, min_size=500_000, audit=audit)
    assert result.id == close.id and result.execution is None
    assert result.prior_reduction.event_id == trim.id
    assert audit[trim.id] == "context_in_close"
    _, lines = format_whale_move_lines(result)
    assert any("No confirmed fill price" in line for line in lines)
    assert any("Earlier trim" in line and "7000 → 3500 ZEC" in line for line in lines)
    assert select(trim, close.model_copy(update={"previous_quantity": 3499}))[0].prior_reduction is None
    assert select(trim.model_copy(update={"execution": None}), close)[0].prior_reduction is None


def test_verified_large_trim_bypasses_previous_small_trim_cooldown():
    policy = PositionPushPolicy()
    small = move("small", 2, 100, 88, "0xa", position_change="reduce")
    assert policy.select([small], now=NOW, min_size=500_000)
    large = move("large", -2, 88, 54, "0xb", position_change="reduce")
    result, = policy.select([small, large], now=NOW + timedelta(minutes=5), min_size=500_000)
    assert result.grouped_event_ids == [large.id]
    assert result.execution.verified and result.size_delta_usd == -3_400_000


def test_unverified_rebound_keeps_large_trim_and_latest_position_snapshot():
    policy = PositionPushPolicy()
    trim = move("trim", 4, 100, 60, "0xa", position_change="reduce")
    rebound = move("rebound", 2, 60, 85, "0xb", execution=None)
    audit = {}
    result, = policy.select([trim, rebound], now=NOW, min_size=500_000, audit=audit)
    assert result.id == trim.id and result.priority_reduction
    assert result.execution == trim.execution and result.size_delta_usd == trim.size_delta_usd
    assert result.size_usd == rebound.size_usd and result.position_observed_at == rebound.timestamp
    assert audit[trim.id] == "verified_reduction_before_unverified_rebound"
    assert policy.select([trim, rebound], now=NOW + timedelta(minutes=2), min_size=500_000) == []


def test_verified_rebound_or_close_supersedes_large_trim():
    trim = move("trim", 4, 100, 60, "0xa", position_change="reduce")
    rebound = move("rebound", 2, 60, 85, "0xb")
    for change in ("increase", "close", "flip"):
        result = PositionPushPolicy().select(
            [trim, rebound.model_copy(update={"position_change": change})], now=NOW, min_size=500_000,
        )
        assert all(a.id != trim.id and trim.id not in a.grouped_event_ids for a in result)


def test_already_selected_large_trim_is_not_rescued_after_rebound():
    policy = PositionPushPolicy()
    trim = move("trim", 2, 100, 60, "0xa", position_change="reduce")
    assert policy.select([trim], now=NOW, min_size=500_000)
    rebound = move("rebound", -1, 60, 85, "0xb", execution=None)
    assert policy.select([trim, rebound], now=NOW + timedelta(minutes=5), min_size=500_000) == []


def test_old_or_unverified_large_trim_is_not_rescued():
    trim = move("trim", 4, 100, 60, "0xa", position_change="reduce")
    rebound = move("rebound", 2, 60, 85, "0xb", execution=None)
    for updates, now in (({"execution": None}, NOW), ({}, NOW + timedelta(minutes=4))):
        assert PositionPushPolicy().select(
            [trim.model_copy(update=updates), rebound], now=now, min_size=500_000,
        ) == []
