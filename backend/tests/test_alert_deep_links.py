from app.config import settings
from app.services.alerts import _alert_detail_link


def test_alert_deep_links_match_the_alert_evidence(monkeypatch) -> None:
    monkeypatch.setattr(settings, "public_app_url", "https://app.hyperpulse.example/")

    assert _alert_detail_link("whale_move_entry", {"trader_address": "0xabc"}) == (
        "https://app.hyperpulse.example/traders/0xabc"
    )
    assert _alert_detail_link("liq_proximity", {"asset": "BTC"}) == (
        "https://app.hyperpulse.example/liquidations"
    )
    assert _alert_detail_link("market_brief", None) == "https://app.hyperpulse.example/insights"


def test_alert_deep_links_are_omitted_without_a_public_http_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "public_app_url", "hyperpulse.local")

    assert _alert_detail_link("market_brief", None) is None
