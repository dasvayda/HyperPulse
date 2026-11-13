from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.services.brief_changes import compare_briefs

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def evidence():
    return {
        "inputs": {
            "top3_consensus": {"assets": ["BTC"], "per_asset": [{"asset": "BTC", "long_pct": 50}]},
            "tape": {"BTC": {"mark_price": 100, "funding_pct": 0.001, "updated_at": NOW.isoformat()}},
            "book_updated_at": NOW.isoformat(),
        },
        "context": {"positions": [{"asset": "BTC", "trader_address": "0xabc"}]},
    }


def compare(new, old):
    return compare_briefs(new, old, NOW, NOW if old else None)


def test_no_baseline_and_no_change_are_distinct():
    assert compare(evidence(), None)["status"] == "no_baseline"
    assert compare(evidence(), evidence()) == {"status": "unchanged", "changes": []}


def test_two_strongest_changes_with_stable_tie_order():
    old = evidence()
    new = deepcopy(old)
    new["inputs"]["tape"]["BTC"].update(mark_price=102, funding_pct=0.021)
    new["inputs"]["top3_consensus"]["per_asset"][0]["long_pct"] = 60
    result = compare(new, old)
    assert result["status"] == "changed"
    assert [c["metric"] for c in result["changes"]] == ["funding", "mark"]


def test_stale_inputs_and_changed_roster_are_not_comparable():
    old, new = evidence(), evidence()
    new["context"]["positions"][0]["trader_address"] = "0xdef"
    new["inputs"]["top3_consensus"]["per_asset"][0]["long_pct"] = 70
    assert compare(new, old) == {"status": "partial", "changes": []}
    new["inputs"]["tape"]["BTC"]["updated_at"] = (NOW - timedelta(hours=1)).isoformat()
    assert compare(new, old) == {"status": "unavailable", "changes": []}


def test_different_top_assets_are_not_compared():
    old, new = evidence(), evidence()
    new["inputs"]["top3_consensus"]["assets"] = ["ETH"]
    assert compare(new, old)["status"] == "unavailable"
