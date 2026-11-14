from datetime import timedelta
import json

from scripts.replay_whale_alerts import replay
from tests.test_whale_alert_selection import NOW, move


def rows(*alerts):
    return [(a.model_dump_json(), a.timestamp.isoformat()) for a in alerts]


def test_unknown_history_is_not_counted_as_suppression():
    alert = move("a", 2, 30, 36, "0xa")
    data = alert.model_dump(mode="json", exclude={"position_change", "previous_quantity", "current_quantity"})
    report = replay([(json.dumps(data), alert.timestamp.isoformat())], 500_000, 120)
    assert report["unreplayable_records"] == 1
    assert report["missing_fields"]["previous_quantity"] == 1
    assert report["new_candidates"] is None


def test_same_bucket_merges_and_adjacent_buckets_can_repeat():
    a, b = move("a", 4, 30, 36, "0xa"), move("b", 2, 36, 42, "0xb")
    report = replay(rows(a, b), 500_000, 60)
    assert report["new_candidates"] == 1
    assert report["max_selection_delay_seconds"] == 120
    next_bucket = b.model_copy(update={"timestamp": NOW + timedelta(minutes=1)})
    assert replay(rows(a, next_bucket), 500_000, 60)["new_candidates"] == 2
