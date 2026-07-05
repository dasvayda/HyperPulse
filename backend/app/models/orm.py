from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TraderRow(Base):
    __tablename__ = "traders"

    address: Mapped[str] = mapped_column(String(64), primary_key=True)
    alias: Mapped[str] = mapped_column(String(128))
    rank: Mapped[int] = mapped_column(Integer, default=0)
    pnl_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    account_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    volume_usd: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_hold_hours: Mapped[float] = mapped_column(Float, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    preferred_assets: Mapped[str] = mapped_column(Text, default="[]")
    strategy_tags: Mapped[str] = mapped_column(Text, default="[]")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    sparkline: Mapped[str] = mapped_column(Text, default="[]")
    smart_money_score: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PositionRow(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trader_address: Mapped[str] = mapped_column(String(64), index=True)
    asset: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(16))
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[float] = mapped_column(Float, default=1.0)
    size_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="open")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LiquidationRow(Base):
    __tablename__ = "liquidations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asset: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(16))
    size_usd: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    tx_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketSnapshotRow(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(32), index=True)
    mark_price: Mapped[float] = mapped_column(Float)
    open_interest: Mapped[float] = mapped_column(Float, default=0.0)
    funding_rate: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InferenceRow(Base):
    __tablename__ = "inference_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trader_address: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(128))
    trading_style: Mapped[str] = mapped_column(String(128))
    risk_profile: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(32), default="heuristic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertRow(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    event_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
