from app.collectors.fills import summarize_alert_execution
from app.models.schemas import AlertType, PositionSide


def test_matching_fills_are_verified_and_keep_transaction_hashes() -> None:
    evidence = summarize_alert_execution(
        [
            {
                "coin": "BTC",
                "dir": "Open Short",
                "px": "100000",
                "sz": "2",
                "hash": "0xabc",
            },
            {
                "coin": "BTC",
                "dir": "Open Short",
                "px": "100000",
                "sz": "1",
                "hash": "0xdef",
            },
        ],
        asset="BTC",
        side=PositionSide.SHORT,
        alert_type=AlertType.ENTRY,
        expected_notional_usd=300_000,
    )

    assert evidence is not None
    assert evidence.verified is True
    assert evidence.notional_usd == 300_000
    assert evidence.quantity == 3
    assert evidence.price_low == 100_000
    assert evidence.tx_hashes == ["0xabc", "0xdef"]


def test_mismatched_snapshot_delta_is_not_presented_as_a_verified_fill() -> None:
    evidence = summarize_alert_execution(
        [
            {
                "coin": "ETH",
                "dir": "Open Long",
                "px": "2500",
                "sz": "40",
                "hash": "0xabc",
            }
        ],
        asset="ETH",
        side=PositionSide.LONG,
        alert_type=AlertType.ENTRY,
        expected_notional_usd=300_000,
    )

    assert evidence is not None
    assert evidence.verified is False
    assert evidence.notional_usd == 100_000
    assert evidence.tx_hashes == []
