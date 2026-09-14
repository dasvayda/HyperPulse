from app.services.brief_report import slice_snapshot, tab_assets, build_tldr_slots
from tests.conftest import sample_snapshot


def test_eth_slice_does_not_cite_btc_in_tldr():
    sliced = slice_snapshot(sample_snapshot(), "ETH")
    tldr = build_tldr_slots(sliced, "ETH")
    blob = f"{tldr.now} {tldr.short_read} {tldr.however}"
    assert "BTC" not in blob
    assert "ETH" in tldr.now
    assert sliced["coverage"]["positioned"] == 14


def test_tab_assets_follow_snapshot_top3():
    snap = sample_snapshot()
    assert tab_assets(snap) == ["HYPE", "BTC", "ETH"]
    sliced = slice_snapshot(snap, "ETH")
    assert sliced["_market_tabs"] == ["HYPE", "BTC", "ETH"]
