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
from app.models.orm import (
    AlertRow,
    InferenceRow,
    LiquidationRow,
    MarketSnapshotRow,
    PositionRow,
    TraderRow,
)
from app.models.schemas import (
    AlertHistoryItem,
    DashboardStats,
    LiquidationEvent,
    LiquidationZone,
    MarketInsight,
    OpenPosition,
    PipelineStatus,
    PositionSide,
    SmartMoneyRank,
    StrategyInference,
    TraderDetail,
    TraderProfile,
    WhaleAlert,
    WhaleBookSummary,
    WhalePosition,
)
from app.services.whale_book import index_positions_by_trader, summarize_whale_book


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _latest_mark_prices(assets: set[str]) -> dict[str, float]:
    if not assets:
        return {}
    db = SessionLocal()
    try:
        marks: dict[str, float] = {}
        for asset in assets:
            row = (
                db.query(MarketSnapshotRow)
                .filter(MarketSnapshotRow.asset == asset)
                .order_by(MarketSnapshotRow.timestamp.desc())
                .first()
            )
            if row is not None:
                marks[asset] = float(row.mark_price)
        return marks
    finally:
        db.close()


def _position_roi(
    *,
    side: PositionSide,
    entry_price: float,
    mark_price: float,
    size_usd: float,
    leverage: float,
) -> tuple[float | None, float | None]:
    """Return (roi_pct, unrealized_pnl_usd).

    ROI is side-aware entry-vs-mark price move, scaled by leverage
    (approx. margin ROI). uPnL assumes size_usd is current notional.
    """
    if entry_price <= 0 or mark_price <= 0 or size_usd <= 0:
        return None, None
    price_move = (mark_price - entry_price) / entry_price
    if side == PositionSide.SHORT:
        price_move = -price_move
    lev = leverage if leverage > 0 else 1.0
    roi_pct = round(price_move * lev * 100.0, 2)
    # size_usd ~= qty * mark  =>  qty = size_usd / mark
    # long pnl = qty * (mark - entry); short pnl = qty * (entry - mark)
    qty = size_usd / mark_price
    if side == PositionSide.LONG:
        unrealized = qty * (mark_price - entry_price)
    else:
        unrealized = qty * (entry_price - mark_price)
    return roi_pct, round(unrealized, 2)


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
        self.whale_positions: list[WhalePosition] = []
        self.whale_positions_by_trader: dict[str, list[WhalePosition]] = {}
        self.whale_summary: WhaleBookSummary | None = None
        # Latest per-asset Hyperliquid ctx (volume/funding/mark) for live Coin Pulse.
        self.market_ticks: dict[str, dict] = {}
        self.last_collect_at: datetime | None = None
        self.last_inference_at: datetime | None = None
        self.last_ranking_at: datetime | None = None
        self.last_alert_at: datetime | None = None
        self.last_consensus_label: str | None = None
        self.last_consensus_at: datetime | None = None
        self.last_brief_telegram_hash: str | None = None
        self.ai_provider: str = "heuristic"
        self.market_brief = None  # MarketBrief | None — set after import-safe bootstrap

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

            # Consensus pulses only fire on mood change, so a restart must not
            # replay the mood that was already sent.
            last_consensus = (
                db.query(AlertRow)
                .filter(AlertRow.event_type == "market_consensus")
                .order_by(AlertRow.created_at.desc())
                .first()
            )
            if last_consensus is not None:
                mood = None
                try:
                    mood = (json.loads(last_consensus.payload or "{}") or {}).get("mood")
                except (TypeError, ValueError):
                    mood = None
                if not mood and last_consensus.title:
                    _, _, tail = last_consensus.title.partition("·")
                    mood = tail.strip() or None
                if mood:
                    self.last_consensus_label = str(mood)
                    self.last_consensus_at = last_consensus.created_at

            last_brief_tg = (
                db.query(AlertRow)
                .filter(AlertRow.event_type == "market_brief")
                .order_by(AlertRow.created_at.desc())
                .first()
            )
            if last_brief_tg is not None:
                try:
                    payload = json.loads(last_brief_tg.payload or "{}") or {}
                    snap_hash = payload.get("snapshot_hash")
                    if snap_hash:
                        self.last_brief_telegram_hash = str(snap_hash)
                except (TypeError, ValueError):
                    pass

            try:
                from app.services.market_brief import load_market_brief_from_db

                self.market_brief = load_market_brief_from_db()
            except Exception:
                self.market_brief = None
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

    def update_whale_book(self, positions: list[WhalePosition], updated_at: datetime | None = None) -> None:
        with self._lock:
            self.whale_positions = positions
            self.whale_positions_by_trader = index_positions_by_trader(positions)
            self.whale_summary = summarize_whale_book(
                positions=positions,
                tracked=len(self.traders),
                updated_at=updated_at,
            )

    def upsert_trader_positions(self, address: str, positions: list[WhalePosition]) -> None:
        """Replace one trader's open positions inside the whale book cache."""
        needle = address.lower()
        with self._lock:
            for key in [k for k in list(self.whale_positions_by_trader) if k.lower() == needle]:
                self.whale_positions_by_trader.pop(key, None)
            if positions:
                canonical = positions[0].trader_address
                self.whale_positions_by_trader[canonical] = list(positions)
            self.whale_positions = [
                p for ps in self.whale_positions_by_trader.values() for p in ps
            ]
            self.whale_summary = summarize_whale_book(
                positions=self.whale_positions,
                tracked=len(self.traders),
            )

    def get_inference(self, address: str) -> StrategyInference | None:
        needle = address.lower()
        for item in self.inferences:
            if item.trader_address.lower() == needle:
                return item
        return None

    def get_open_positions(self, address: str) -> list[WhalePosition]:
        needle = address.lower()
        direct = self.whale_positions_by_trader.get(address)
        if direct is not None:
            return direct
        for key, positions in self.whale_positions_by_trader.items():
            if key.lower() == needle:
                return positions
        return []

    def summarize_open_pnl(self, address: str) -> tuple[float | None, float | None]:
        """Return (open_roi_pct, open_unrealized_pnl_usd) for a trader.

        Portfolio ROI approximates margin ROI: sum(uPnL) / sum(notional/leverage).
        """
        positions = self.get_open_positions(address)
        if not positions:
            return None, None
        marks = _latest_mark_prices({p.asset for p in positions})
        total_upnl = 0.0
        total_margin = 0.0
        priced = 0
        for pos in positions:
            mark = marks.get(pos.asset)
            if mark is None:
                continue
            roi_pct, upnl = _position_roi(
                side=pos.side,
                entry_price=pos.entry_price,
                mark_price=mark,
                size_usd=pos.size_usd,
                leverage=pos.leverage,
            )
            if upnl is None:
                continue
            total_upnl += upnl
            lev = pos.leverage if pos.leverage > 0 else 1.0
            total_margin += pos.size_usd / lev
            priced += 1
        if priced == 0:
            return None, None
        if total_margin <= 0:
            return None, round(total_upnl, 2)
        open_roi = round(total_upnl / total_margin * 100.0, 2)
        return open_roi, round(total_upnl, 2)

    def get_trader_detail(
        self,
        address: str,
        *,
        open_positions: list[OpenPosition] | None = None,
        open_positions_raw: list[WhalePosition] | None = None,
    ) -> TraderDetail | None:
        needle = address.lower()
        for trader in self.traders:
            if trader.address.lower() != needle:
                continue
            recent = [
                a for a in self.whale_alerts if a.trader_address.lower() == needle
            ][:5]
            recent_positions = [
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
            if open_positions is None:
                open_raw = (
                    open_positions_raw
                    if open_positions_raw is not None
                    else self.get_open_positions(trader.address)
                )
                marks = _latest_mark_prices({p.asset for p in open_raw})
                open_positions = []
                for p in sorted(open_raw, key=lambda pos: pos.size_usd, reverse=True):
                    mark = marks.get(p.asset)
                    roi_pct = None
                    unrealized = None
                    if mark is not None:
                        roi_pct, unrealized = _position_roi(
                            side=p.side,
                            entry_price=p.entry_price,
                            mark_price=mark,
                            size_usd=p.size_usd,
                            leverage=p.leverage,
                        )
                    open_positions.append(
                        OpenPosition(
                            asset=p.asset,
                            side=p.side,
                            size_usd=p.size_usd,
                            entry_price=p.entry_price,
                            leverage=p.leverage,
                            mark_price=mark,
                            roi_pct=roi_pct,
                            unrealized_pnl_usd=unrealized,
                        )
                    )
            preferred = trader.preferred_assets or sorted(
                {p.asset for p in open_positions}
            )
            inference = self.get_inference(trader.address)
            if inference:
                primary_label = inference.strategy
            elif trader.strategy_tags:
                primary_label = trader.strategy_tags[0]
            else:
                primary_label = "active"
            assets_label = ", ".join(preferred) if preferred else "n/a"
            parts = [f"{trader.alias} is a {primary_label.lower()} trader."]
            # Win rate / trade count / hold time are only meaningful when collected.
            # Live Hyperliquid leaderboard does not provide them (stay at 0).
            if trader.total_trades > 0:
                hold = (
                    f", avg hold {trader.avg_hold_hours:.1f}h"
                    if trader.avg_hold_hours > 0
                    else ""
                )
                parts.append(
                    f"Recorded {trader.win_rate:.1f}% win rate over "
                    f"{trader.total_trades} trades{hold}."
                )
            parts.append(
                f"All-time PnL ${trader.pnl_usd:,.0f} "
                f"({trader.pnl_change_pct:+.1f}% ROI)."
            )
            if preferred:
                parts.append(f"Active on {assets_label}.")
            if open_positions:
                open_notional = sum(p.size_usd for p in open_positions)
                parts.append(
                    f"Currently holds {len(open_positions)} open position(s) "
                    f"totaling ${open_notional:,.0f}."
                )
            if inference:
                parts.append(
                    f"AI classifies style as {inference.trading_style} "
                    f"({inference.strategy}) with {inference.confidence:.0f}% confidence."
                )
            summary = " ".join(parts)

            rank_row = next(
                (r for r in self.rankings if r.address.lower() == needle),
                None,
            )
            open_roi, open_upnl = self.summarize_open_pnl(trader.address)
            if rank_row and rank_row.open_roi_pct is not None:
                open_roi = rank_row.open_roi_pct
            if rank_row and rank_row.open_unrealized_pnl_usd is not None:
                open_upnl = rank_row.open_unrealized_pnl_usd
            if open_upnl is None and open_positions:
                if any(p.unrealized_pnl_usd is not None for p in open_positions):
                    open_upnl = round(
                        sum(p.unrealized_pnl_usd or 0.0 for p in open_positions), 2
                    )
            if open_roi is None and open_positions:
                scored = [p for p in open_positions if p.roi_pct is not None]
                total = sum(p.size_usd for p in scored)
                if total > 0:
                    open_roi = round(
                        sum((p.roi_pct or 0.0) * p.size_usd for p in scored) / total, 2
                    )

            max_lev = max((p.leverage for p in open_positions), default=None)
            avg_lev = (
                round(sum(p.leverage for p in open_positions) / len(open_positions), 2)
                if open_positions
                else None
            )
            from app.services.copy_check import compute_copy_verdict

            copy = compute_copy_verdict(
                smart_money_score=rank_row.smart_money_score if rank_row else None,
                open_roi_pct=open_roi,
                open_unrealized_pnl_usd=open_upnl,
                max_leverage=max_lev,
                risk_score=trader.risk_score,
                inference_confidence=inference.confidence if inference else None,
                open_positions=open_positions,
            )

            data = trader.model_dump()
            data["preferred_assets"] = preferred
            return TraderDetail(
                **data,
                recent_positions=recent_positions,
                open_positions=open_positions,
                behavior_summary=summary,
                inferred_strategy=inference.strategy if inference else None,
                inferred_trading_style=inference.trading_style if inference else None,
                inference_confidence=inference.confidence if inference else None,
                smart_money_score=rank_row.smart_money_score if rank_row else None,
                open_roi_pct=open_roi,
                open_unrealized_pnl_usd=open_upnl,
                avg_leverage=avg_lev,
                max_leverage=max_lev,
                copy_verdict=copy.verdict,
                copy_reasons=copy.reasons,
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
            whales_positioned=self.whale_summary.with_positions if self.whale_summary else None,
            whale_long_pct=self.whale_summary.long_pct if self.whale_summary else None,
            whale_net_bias=self.whale_summary.net_bias if self.whale_summary else None,
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
