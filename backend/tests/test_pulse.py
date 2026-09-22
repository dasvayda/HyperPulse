"""Unit tests for short-horizon pulse (rules_v1)."""

from datetime import datetime, timedelta, timezone

from app.db import SessionLocal, init_db
from app.models.orm import MarketSnapshotRow, PulseResultRow, PulseSignalRow
from app.models.schemas import InsightStance, PulseDirection
from app.services.pulse import (
    EXPIRE_GRACE_SEC,
    HORIZON_SEC,
    emit_pulse_for_asset,
    get_pulse_snapshot,
    probabilities_from_votes,
    resolve_due_pulses,
)

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
ASSET = "ZZPULSE"


def _cleanup():
    db = SessionLocal()
    try:
        ids = [
            r.id
            for r in db.query(PulseSignalRow).filter(PulseSignalRow.asset == ASSET).all()
        ]
        if ids:
            db.query(PulseResultRow).filter(PulseResultRow.signal_id.in_(ids)).delete(
                synchronize_session=False
            )
            db.query(PulseSignalRow).filter(PulseSignalRow.asset == ASSET).delete(
                synchronize_session=False
            )
        db.query(MarketSnapshotRow).filter(MarketSnapshotRow.asset == ASSET).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def setup_module(_mod):
    init_db()
    _cleanup()


def teardown_module(_mod):
    _cleanup()


def test_probabilities_sum_to_one_and_buy_leans_up():
    direction, p_up, p_down, p_wait = probabilities_from_votes(
        [InsightStance.BUY, InsightStance.BUY, InsightStance.HOLD],
        InsightStance.BUY,
    )
    assert abs(p_up + p_down + p_wait - 1.0) < 1e-6
    assert direction == PulseDirection.UP
    assert p_up > p_down
    assert p_up > p_wait or p_wait >= 0.1


def test_hold_votes_keep_wait():
    direction, p_up, p_down, p_wait = probabilities_from_votes(
        [InsightStance.HOLD, InsightStance.HOLD],
        InsightStance.HOLD,
    )
    assert direction == PulseDirection.WAIT
    assert p_wait >= p_up and p_wait >= p_down


def test_prefer_conflict_tilts_wait():
    # Votes say sell, Prefer badge is buy → wait tilt.
    direction, _u, _d, p_wait = probabilities_from_votes(
        [InsightStance.SELL, InsightStance.SELL],
        InsightStance.BUY,
    )
    assert direction == PulseDirection.WAIT
    assert p_wait >= 0.3


def test_emit_and_resolve_hit_up():
    _cleanup()
    emit = emit_pulse_for_asset(
        asset=ASSET,
        votes=[InsightStance.BUY, InsightStance.BUY],
        card_stance=InsightStance.BUY,
        mark_price=100.0,
        now=NOW,
    )
    assert emit is not None
    assert abs(emit.p_up + emit.p_down + emit.p_wait - 1.0) < 1e-3
    assert emit.direction == "up"

    due = NOW + timedelta(seconds=HORIZON_SEC)
    db = SessionLocal()
    try:
        db.add(
            MarketSnapshotRow(
                asset=ASSET,
                mark_price=101.0,  # +100 bps → up
                open_interest=1.0,
                funding_rate=0.0,
                day_volume_usd=1.0,
                timestamp=due + timedelta(seconds=30),
            )
        )
        db.commit()
    finally:
        db.close()

    # Must not use future price before due — resolve at emit time should skip.
    assert resolve_due_pulses(now=NOW + timedelta(minutes=5)) == 0

    n = resolve_due_pulses(now=due + timedelta(minutes=1))
    assert n == 1

    db = SessionLocal()
    try:
        result = db.query(PulseResultRow).filter(PulseResultRow.signal_id == emit.id).one()
        assert result.outcome == "up"
        assert result.hit == 1
        assert result.return_bps is not None and result.return_bps > 50
    finally:
        db.close()

    snap = get_pulse_snapshot(ASSET, now=due + timedelta(minutes=1))
    assert snap is not None
    assert snap.direction == PulseDirection.UP
    assert snap.status.value in {"resolved", "open", "stale"}


def test_resolve_flat_and_expired():
    _cleanup()
    emit = emit_pulse_for_asset(
        asset=ASSET,
        votes=[InsightStance.BUY, InsightStance.HOLD],
        card_stance=InsightStance.BUY,
        mark_price=100.0,
        now=NOW,
    )
    assert emit is not None

    due = NOW + timedelta(seconds=HORIZON_SEC)
    db = SessionLocal()
    try:
        db.add(
            MarketSnapshotRow(
                asset=ASSET,
                mark_price=100.02,  # +2 bps → flat
                open_interest=1.0,
                funding_rate=0.0,
                day_volume_usd=1.0,
                timestamp=due + timedelta(seconds=10),
            )
        )
        db.commit()
    finally:
        db.close()

    assert resolve_due_pulses(now=due + timedelta(minutes=1)) == 1
    db = SessionLocal()
    try:
        result = db.query(PulseResultRow).filter(PulseResultRow.signal_id == emit.id).one()
        assert result.outcome == "flat"
        assert result.hit == 0  # directional pulse: flat is miss
    finally:
        db.close()

    _cleanup()
    emit2 = emit_pulse_for_asset(
        asset=ASSET,
        votes=[InsightStance.SELL, InsightStance.SELL],
        card_stance=InsightStance.SELL,
        mark_price=50.0,
        now=NOW,
    )
    assert emit2 is not None
    # No snapshot past due → expire after grace.
    expire_at = NOW + timedelta(seconds=EXPIRE_GRACE_SEC + 60)
    assert resolve_due_pulses(now=expire_at) == 1
    db = SessionLocal()
    try:
        result = db.query(PulseResultRow).filter(PulseResultRow.signal_id == emit2.id).one()
        assert result.outcome == "expired"
        assert result.hit is None
    finally:
        db.close()


def test_wait_hits_on_flat():
    _cleanup()
    emit = emit_pulse_for_asset(
        asset=ASSET,
        votes=[InsightStance.HOLD, InsightStance.HOLD],
        card_stance=InsightStance.HOLD,
        mark_price=200.0,
        now=NOW,
    )
    assert emit is not None
    assert emit.direction == "wait"

    due = NOW + timedelta(seconds=HORIZON_SEC)
    db = SessionLocal()
    try:
        db.add(
            MarketSnapshotRow(
                asset=ASSET,
                mark_price=200.01,
                open_interest=1.0,
                funding_rate=0.0,
                day_volume_usd=1.0,
                timestamp=due + timedelta(seconds=5),
            )
        )
        db.commit()
    finally:
        db.close()

    assert resolve_due_pulses(now=due + timedelta(minutes=1)) == 1
    db = SessionLocal()
    try:
        result = db.query(PulseResultRow).filter(PulseResultRow.signal_id == emit.id).one()
        assert result.outcome == "flat"
        assert result.hit == 1
    finally:
        db.close()
