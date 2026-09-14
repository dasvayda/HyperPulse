from app.services.brief_report import pick_however
from tests.conftest import sample_snapshot


def test_quiet_1h_and_skewed_24h_goes_to_however():
    snap = sample_snapshot()
    snap["liq_1h"] = {"long_usd": 10_000, "short_usd": 8_000, "total_usd": 18_000, "events": 2}
    snap["liq_24h"] = {"long_usd": 8e6, "short_usd": 1e6, "total_usd": 9e6, "events": 40}
    snap["tape"]["HYPE"]["change_pct_24h"] = -0.2
    text = pick_however(snap, asset=None)
    assert "24h" in text
    assert "long-flush" in text
