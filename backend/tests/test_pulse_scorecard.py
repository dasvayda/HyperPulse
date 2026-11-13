from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models.orm import MarketSnapshotRow, PulseSignalRow
from app.models.schemas import InsightStance
from app.services.pulse import resolve_due_pulses, save_scorecard_signal
from app.services.pulse_scorecard import scorecard


def test_scorecard_keeps_all_outcomes_and_rejects_late_observations():
    now = datetime(2097, 1, 1, tzinfo=timezone.utc)
    with SessionLocal() as db:
        for asset, vote, mark, seconds in [
            ("V07HIT", InsightStance.BUY, 101, 901),
            ("V07MISS", InsightStance.BUY, 99, 900),
            ("V07WAIT", InsightStance.HOLD, 102, 1020),
            ("V07LATE", InsightStance.SELL, 99, 1021),
            ("V07PENDING", InsightStance.BUY, None, 0),
        ]:
            at = now + timedelta(seconds=600 if asset == "V07PENDING" else 0)
            save_scorecard_signal(db, asset=asset, votes=[vote], card_stance=vote,
                                  mark_price=100, mark_at=at, now=at, evidence_id="saved")
            if mark:
                db.add(MarketSnapshotRow(asset=asset, mark_price=mark, open_interest=1,
                                         funding_rate=0, day_volume_usd=1,
                                         timestamp=now + timedelta(seconds=seconds)))
        db.add(PulseSignalRow(id="v07-old", asset="V07OLD", direction="up", mark_at_emit=100, created_at=now))
        db.commit()
    end = now + timedelta(seconds=1100)
    resolve_due_pulses(end)
    assert resolve_due_pulses(end) == 0
    result = scorecard(None, 1, 0, 2, now=end)
    assert result["counts"] == {"hit": 1, "miss": 1, "wait": 1, "pending": 1, "unavailable": 1}
    assert result["directional_evaluated"] == 2 and len(result["items"]) == 2
    late = scorecard("V07LATE", 1, 0, 25, now=end)["items"][0]
    assert late["observed_at"] is None and late["result_mark"] is None
    assert scorecard("V07OLD", 1, 0, 25, now=end)["total"] == 0
    # Remove only this fixture's rows, including their resolutions and marks.
    from app.models.orm import PulseResultRow
    with SessionLocal() as db:
        ids = [row.id for row in db.query(PulseSignalRow).filter(PulseSignalRow.asset.like("V07%"))]
        db.query(PulseResultRow).filter(PulseResultRow.signal_id.in_(ids)).delete(synchronize_session=False)
        db.query(PulseSignalRow).filter(PulseSignalRow.id.in_(ids)).delete(synchronize_session=False)
        db.query(MarketSnapshotRow).filter(MarketSnapshotRow.asset.like("V07%")).delete(synchronize_session=False)
        db.commit()
