from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from threading import Lock

from sqlalchemy.orm import Session

from app.config import settings
from app.data.seed import (
    DASHBOARD_STATS,
    LIQUIDATION_EVENTS,
    LIQUIDATION_ZONES,
    TRADERS,
    WHALE_ALERTS,
)
from app.db import SessionLocal
from app.models.orm import AlertRow, InferenceRow, LiquidationRow, PositionRow, TraderRow
from app.models.schemas import (
    AlertHistoryItem,
    DashboardStats,
    LiquidationEvent,
    LiquidationZone,
    MarketInsight,
    PipelineStatus,
    SmartMoneyRank,
    StrategyInference,
    TraderDetail,
    TraderProfile,
    WhaleAlert,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _is_real_address(address: str | None) -> bool:
    if not address:
        return False
    return bool(_ADDRESS_RE.match(address))


class StateStore:
    """In-memory state with optional SQLAlchemy persistence."""

    def __init__(self) -> None:
        self._lock = Lock()

        if settings.use_mock_data:
            self.whale_alerts: list[WhaleAlert] = list(WHALE_ALERTS)
            self.traders: list[TraderProfile] = list(TRADERS)
            self.liquidation_zones: list[LiquidationZone] = list(LIQUIDATION_ZONES)
            self.liquidation_events: list[LiquidationEvent] = list(LIQUIDATION_EVENTS)
            self.dashboard = DASHBOARD_STATS.model_copy()
        else:
            self.whale_alerts = []
            self.traders = []
            self.liquidation_zones = []
            self.liquidation_events = []
            self.dashboard = DashboardStats(
                active_whales=0,
                alerts_24h=0,
                total_liquidations_24h=0.0,
                top_asset="BTC",
            )

        self.inferences: list[StrategyInference] = []
        self.rankings: list[SmartMoneyRank] = []
        self.insights: list[MarketInsight] = []
        self.alerts: list[AlertHistoryItem] = []
        self.last_collect_at: datetime | None = None
        self.last_inference_at: datetime | None = None
        self.last_ranking_at: datetime | None = None
        self.last_alert_at: datetime | None = None
        self.ai_provider: str = "heuristic"

    def bootstrap_from_db(self) -> None:
        db = SessionLocal()
        try:
            traders = db.query(TraderRow).order_by(TraderRow.rank.asc()).all()
            if traders:
                filtered = [t for t in traders if _is_real_address(t.address)]
                self.traders = [self._trader_from_row(t) for t in filtered]

            inferences = (
                db.query(InferenceRow)
                .order_by(InferenceRow.created_at.desc())
                .limit(100)
                .all()
            )
            alias_map = {t.address: t.alias for t in self.traders}
            self.inferences = [
                StrategyInference(
                    id=row.id,
                    trader_address=row.trader_address,
                    trader_alias=alias_map.get(row.trader_address, row.trader_address),
                    strategy=row.strategy,
                    trading_style=row.trading_style,
                    risk_profile=row.risk_profile,
                    confidence=row.confidence,
                    rationale=row.rationale,
                    provider=row.provider,
                    created_at=row.created_at,
                )
                for row in inferences
            ]

            alerts = (
                db.query(AlertRow).order_by(AlertRow.created_at.desc()).limit(100).all()
            )
            self.alerts = [
                AlertHistoryItem(
                    id=row.id,
                    channel=row.channel,
                    event_type=row.event_type,
                    title=row.title,
                    message=row.message,
                    status=row.status,
                    created_at=row.created_at,
                    sent_at=row.sent_at,
                )
                for row in alerts
            ]
        finally:
            db.close()

    def persist_traders(self, traders: list[TraderProfile], scores: dict[str, float] | None = None) -> None:
        scores = scores or {}
        db = SessionLocal()
        try:
            for trader in traders:
                row = db.get(TraderRow, trader.address)
                if row is None:
                    row = TraderRow(address=trader.address)
                    db.add(row)
                row.alias = trader.alias
                row.rank = trader.rank
                row.pnl_usd = trader.pnl_usd
                row.pnl_change_pct = trader.pnl_change_pct
                row.account_value_usd = trader.account_value_usd
                row.volume_usd = trader.volume_usd
                row.win_rate = trader.win_rate
                row.avg_hold_hours = trader.avg_hold_hours
                row.total_trades = trader.total_trades
                row.preferred_assets = json.dumps(trader.preferred_assets)
                row.strategy_tags = json.dumps(trader.strategy_tags)
                row.risk_score = trader.risk_score
                row.sparkline = json.dumps(trader.sparkline)
                row.smart_money_score = scores.get(trader.address, 0.0)
                row.updated_at = _utcnow()
            db.commit()
        finally:
            db.close()

    def persist_inference(self, item: StrategyInference) -> None:
        db = SessionLocal()
        try:
            db.add(
                InferenceRow(
                    id=item.id,
                    trader_address=item.trader_address,
                    strategy=item.strategy,
                    trading_style=item.trading_style,
                    risk_profile=item.risk_profile,
                    confidence=item.confidence,
                    rationale=item.rationale,
                    provider=item.provider,
                    created_at=item.created_at,
                )
            )
            db.commit()
        finally:
            db.close()

    def persist_alert(self, item: AlertHistoryItem, payload: dict | None = None) -> None:
        db = SessionLocal()
        try:
            db.add(
                AlertRow(
                    id=item.id,
                    channel=item.channel,
                    event_type=item.event_type,
                    title=item.title,
                    message=item.message,
                    payload=json.dumps(payload or {}),
                    status=item.status,
                    created_at=item.created_at,
                    sent_at=item.sent_at,
                )
            )
            db.commit()
        finally:
            db.close()

    def persist_liquidations(self, events: list[LiquidationEvent]) -> None:
        db = SessionLocal()
        try:
            for event in events:
                if db.get(LiquidationRow, event.id):
                    continue
                db.add(
                    LiquidationRow(
                        id=event.id,
                        asset=event.asset,
                        side=event.side.value,
                        size_usd=event.size_usd,
                        price=event.price,
                        tx_hash=event.tx_hash,
                        timestamp=event.timestamp,
                    )
                )
            db.commit()
        finally:
            db.close()

    def persist_positions_from_alerts(self, alerts: list[WhaleAlert]) -> None:
        db = SessionLocal()
        try:
            for alert in alerts:
                if db.get(PositionRow, alert.id):
                    continue
                db.add(
                    PositionRow(
                        id=alert.id,
                        trader_address=alert.trader_address,
                        asset=alert.asset,
                        side=alert.side.value,
                        entry_price=alert.entry_price,
                        exit_price=alert.exit_price,
                        leverage=alert.leverage,
                        size_usd=alert.size_usd,
                        status="closed" if alert.alert_type.value == "exit" else "open",
                        timestamp=alert.timestamp,
                    )
                )
            db.commit()
        finally:
            db.close()

    def get_trader_detail(self, address: str) -> TraderDetail | None:
        for trader in self.traders:
            if trader.address == address:
                recent = [a for a in self.whale_alerts if a.trader_address == address][:5]
                positions = [
                    {
                        "asset": a.asset,
                        "side": a.side.value,
                        "type": a.alert_type.value,
                        "size_usd": a.size_usd,
                        "price": a.entry_price or a.exit_price,
                        "timestamp": a.timestamp.isoformat(),
                    }
                    for a in recent
                ]
                inference = next(
                    (i for i in self.inferences if i.trader_address == address),
                    None,
                )
                primary_tag = trader.strategy_tags[0] if trader.strategy_tags else "active"
                summary = (
                    f"{trader.alias} is a {primary_tag.lower()} trader "
                    f"with {trader.win_rate}% win rate over {trader.total_trades} trades. "
                    f"Prefers {', '.join(trader.preferred_assets)} with avg hold time "
                    f"of {trader.avg_hold_hours}h."
                )
                if inference:
                    summary = (
                        f"{summary} AI classifies style as {inference.trading_style} "
                        f"({inference.strategy}) with {inference.confidence:.0f}% confidence."
                    )
                return TraderDetail(
                    **trader.model_dump(),
                    recent_positions=positions,
                    behavior_summary=summary,
                )
        return None

    def refresh_dashboard(self) -> DashboardStats:
        dominant = "Momentum"
        if self.inferences:
            counts: dict[str, int] = {}
            for item in self.inferences:
                counts[item.strategy] = counts.get(item.strategy, 0) + 1
            dominant = max(counts, key=counts.get)  # type: ignore[arg-type]

        avg_score = 0.0
        if self.rankings:
            avg_score = sum(r.smart_money_score for r in self.rankings) / len(self.rankings)

        telegram_count = len(
            [a for a in self.alerts if a.channel == "telegram" and a.status == "sent"]
        )

        source = "mock" if settings.use_mock_data else "mixed"
        self.dashboard = DashboardStats(
            active_whales=len(self.traders),
            alerts_24h=len(self.whale_alerts),
            total_liquidations_24h=sum(e.size_usd for e in self.liquidation_events),
            top_asset=self.dashboard.top_asset,
            dominant_strategy=dominant,
            avg_smart_money_score=round(avg_score, 1),
            telegram_alerts_24h=telegram_count,
            data_source=source,
        )
        return self.dashboard

    def pipeline_status(self) -> PipelineStatus:
        if settings.use_mock_data and self.last_collect_at is None:
            source = "mock"
        elif settings.use_mock_data:
            source = "mixed"
        else:
            source = "live"

        return PipelineStatus(
            collector_enabled=settings.collector_enabled,
            last_collect_at=self.last_collect_at,
            last_inference_at=self.last_inference_at,
            last_ranking_at=self.last_ranking_at,
            last_alert_at=self.last_alert_at,
            telegram_configured=settings.telegram_configured,
            ai_provider=self.ai_provider,
            traders_tracked=len(self.traders),
            inferences_count=len(self.inferences),
            alerts_count=len(self.alerts),
            data_source=source,
        )

    @staticmethod
    def _trader_from_row(row: TraderRow) -> TraderProfile:
        return TraderProfile(
            address=row.address,
            alias=row.alias,
            rank=row.rank,
            pnl_usd=row.pnl_usd,
            pnl_change_pct=row.pnl_change_pct,
            account_value_usd=getattr(row, "account_value_usd", 0.0) or 0.0,
            volume_usd=getattr(row, "volume_usd", 0.0) or 0.0,
            win_rate=row.win_rate,
            avg_hold_hours=row.avg_hold_hours,
            total_trades=row.total_trades,
            preferred_assets=json.loads(row.preferred_assets or "[]"),
            strategy_tags=json.loads(row.strategy_tags or "[]"),
            risk_score=row.risk_score,
            sparkline=json.loads(row.sparkline or "[]"),
        )

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:10]}"


store = StateStore()
