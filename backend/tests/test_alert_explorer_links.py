from app.config import settings
from app.services.alerts import _alert_explorer_link, _alert_explorer_links


def test_position_alerts_link_to_the_wallet_explorer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "hypurrscan_url", "https://hypurrscan.example/")

    assert _alert_explorer_link("whale_move_entry", {"trader_address": "0xabc"}) == (
        "View wallet",
        "https://hypurrscan.example/address/0xabc",
    )


def test_transaction_hash_uses_the_matching_execution_domain(monkeypatch) -> None:
    monkeypatch.setattr(settings, "hypercore_explorer_url", "https://core.example/explorer/")
    monkeypatch.setattr(settings, "hyperevm_explorer_url", "https://evm.example/")

    assert _alert_explorer_link("liquidation_event", {"tx_hash": "0xcore"}) == (
        "View HyperCore tx",
        "https://core.example/explorer/tx/0xcore",
    )
    assert _alert_explorer_link(
        "liquidation_event", {"tx_hash": "0xevm", "chain": "hyperevm"}
    ) == ("View HyperEVM tx", "https://evm.example/tx/0xevm")


def test_explorer_links_require_a_safe_http_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "hypurrscan_url", "file:///local")

    assert _alert_explorer_link("big_trade_entry", {"trader_address": "0xabc"}) is None


def test_verified_fill_hashes_are_linked_before_the_wallet(monkeypatch) -> None:
    monkeypatch.setattr(settings, "hypercore_explorer_url", "https://core.example/explorer")
    monkeypatch.setattr(settings, "hypurrscan_url", "https://wallet.example")

    links = _alert_explorer_links(
        "whale_move_entry",
        {
            "trader_address": "0xabc",
            "execution": {"verified": True, "tx_hashes": ["0xone", "0xtwo"]},
        },
    )

    assert links == [
        ("View verified tx 1/2", "https://core.example/explorer/tx/0xone"),
        ("View verified tx 2/2", "https://core.example/explorer/tx/0xtwo"),
        ("View wallet", "https://wallet.example/address/0xabc"),
    ]
