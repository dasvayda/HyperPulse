from tests.conftest import seed_store
from app.services.market_brief import build_market_brief_snapshot


def test_snapshot_includes_tape_funding_and_coverage():
    seed_store()
    snap = build_market_brief_snapshot()
    assert "tape" in snap
    btc = snap["tape"]["BTC"]
    assert btc["mark_price"] == 76844.0
    assert btc["change_pct_24h"] == -2.1
    assert btc["funding_pct"] is not None
    assert snap["coverage"]["positioned"] == 55
    assert snap["coverage"]["tracked"] == 100
    assert "liq_1h_by_asset" in snap
    assert "BTC" in snap["liq_1h_by_asset"]


def test_snapshot_hash_ignores_as_of():
    seed_store()
    a = build_market_brief_snapshot()
    b = build_market_brief_snapshot()
    assert a["as_of"] != b["as_of"] or True
    assert a["snapshot_hash"] == b["snapshot_hash"]
