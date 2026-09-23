"""Whale-move Telegram copy should spell out size vs Smart Money ranks."""

from datetime import datetime, timedelta, timezone

from app.models.schemas import (
    AlertType,
    PositionSide,
    SmartMoneyRank,
    TraderProfile,
    WhaleAlert,
)
from app.services.alerts import (
    _ordinal,
    _whale_size_context_lines,
    format_whale_move_lines,
)
from app.services.store import store


TARGET = "0xf5d8aaaabbbbccccddddeeeeffff11112222ad53"


def _trader(address: str, account_value_usd: float, rank: int = 1) -> TraderProfile:
    return TraderProfile(
        address=address,
        alias=f"{address[:6]}...{address[-4:]}",
        rank=rank,
        pnl_usd=1.0,
        pnl_change_pct=0.0,
        account_value_usd=account_value_usd,
        win_rate=50.0,
        avg_hold_hours=1.0,
        total_trades=1,
        preferred_assets=["BTC"],
        strategy_tags=[],
        risk_score=50.0,
        sparkline=[1.0],
    )


def _rank(address: str, account_value_usd: float, score: float) -> SmartMoneyRank:
    return SmartMoneyRank(
        address=address,
        alias=f"{address[:6]}...{address[-4:]}",
        rank=1,
        smart_money_score=score,
        pnl_usd=1.0,
        account_value_usd=account_value_usd,
        pnl_change_pct=0.0,
        strategy_tags=[],
        risk_score=50.0,
        momentum_score=50.0,
        consistency_score=50.0,
        sparkline=[1.0],
    )


def _alert(**overrides) -> WhaleAlert:
    base = dict(
        id="wa_test",
        trader_address=TARGET,
        trader_alias="0xf5d8...ad53",
        asset="BTC",
        side=PositionSide.LONG,
        alert_type=AlertType.ENTRY,
        size_usd=2_400_000,
        size_delta_usd=547_000,
        entry_price=86_222,
        leverage=3,
        win_rate=0,
        inferred_strategy="unknown",
        confidence_score=80,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
        whale_long_pct=17.0,
        roi_pct=0.0,
    )
    base.update(overrides)
    return WhaleAlert(**base)


def _book_of_100(*, target_av: float = 68_300_000.0):
    """8th-largest wallet among 100; low Smart Money score among the top 15."""
    traders: list[TraderProfile] = []
    ranks: list[SmartMoneyRank] = []
    # 7 larger wallets, then the target, then 92 smaller.
    for i in range(1, 8):
        addr = f"0x{i:040x}"
        av = target_av + (8 - i) * 1_000_000
        traders.append(_trader(addr, av, rank=i))
        ranks.append(_rank(addr, av, score=90.0 - i))
    traders.append(_trader(TARGET, target_av, rank=8))
    ranks.append(_rank(TARGET, target_av, score=12.0))
    for i in range(9, 101):
        addr = f"0x{i:040x}"
        av = target_av - (i * 100_000)
        traders.append(_trader(addr, av, rank=i))
        # One extra large-wallet peer below the target with an even worse score
        # so the target lands 14th of 15 on the Smart Money board.
        score = 5.0 if i == 9 else 40.0
        ranks.append(_rank(addr, av, score=score))
    return traders, ranks


def test_ordinal_suffixes():
    assert _ordinal(1) == "1st"
    assert _ordinal(2) == "2nd"
    assert _ordinal(3) == "3rd"
    assert _ordinal(4) == "4th"
    assert _ordinal(8) == "8th"
    assert _ordinal(11) == "11th"
    assert _ordinal(12) == "12th"
    assert _ordinal(13) == "13th"
    assert _ordinal(14) == "14th"
    assert _ordinal(21) == "21st"
    assert _ordinal(22) == "22nd"
    assert _ordinal(23) == "23rd"


def test_size_rank_is_wallet_size_not_smart_money(monkeypatch):
    traders, ranks = _book_of_100()
    monkeypatch.setattr(store, "traders", traders)
    monkeypatch.setattr(store, "rankings", ranks)

    lines = _whale_size_context_lines(_alert())
    assert lines[0] == "Wallet $68.3M · 8th largest of 100 tracked"
    assert lines[1] == "Smart Money score: 14th of 15 large wallets"


def test_off_smart_money_board_omits_score_line(monkeypatch):
    traders, ranks = _book_of_100()
    small = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    traders[-1] = _trader(small, 10_000.0, rank=100)
    ranks[-1] = _rank(small, 10_000.0, score=99.0)
    monkeypatch.setattr(store, "traders", traders)
    monkeypatch.setattr(store, "rankings", ranks)

    lines = _whale_size_context_lines(_alert(trader_address=small))
    assert lines == ["Wallet $10K · 100th largest of 100 tracked"]
    assert all("Smart Money" not in line for line in lines)


def test_whale_move_copy_labels_price_delta_and_ranks(monkeypatch):
    traders, ranks = _book_of_100()
    monkeypatch.setattr(store, "traders", traders)
    monkeypatch.setattr(store, "rankings", ranks)

    title, lines = format_whale_move_lines(_alert())
    text = "\n".join(lines)
    assert title == "WHALE MOVE · FRESH ENTRY BTC"
    assert "entered LONG $2.4M @ 3x" in text
    assert "entry $86,222" in text
    assert "added $547K" in text
    assert "Wallet $68.3M · 8th largest of 100 tracked" in text
    assert "Smart Money score: 14th of 15 large wallets" in text
    assert "Tracked BTC whales: 83% short / 17% long" in text
    assert "this pos ROI +0.0%" in text
    assert "Size #" not in text
    assert "Smart Money #" not in text
    assert "AV $" not in text
