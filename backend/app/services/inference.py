from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.models.schemas import (
    InsightStance,
    MarketInsight,
    SmartMoneyRank,
    StrategyInference,
    TraderProfile,
    WhaleAlert,
)
from app.db import SessionLocal
from app.models.orm import MarketSnapshotRow
from app.services.liq_windows import pressure_line, rollup_liq_windows
from app.services.store import store

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _positions_for_trader(address: str):
    return store.get_open_positions(address)


def _funding_stance(funding_pct: float) -> tuple[InsightStance, str, float]:
    """Map funding rate (%) to a simple trade stance.

    Positive funding = longs pay shorts (longs crowded).
    Negative funding = shorts pay longs (shorts crowded).
    Near-zero funding = no directional edge → HOLD.
    """
    if funding_pct >= 0.01:
        return (
            InsightStance.SELL,
            "Funding is elevated - longs look crowded; prefer shorts / cut long risk.",
            min(90.0, 60.0 + funding_pct * 800),
        )
    if funding_pct <= -0.01:
        return (
            InsightStance.BUY,
            "Funding is deeply negative - shorts look crowded; prefer longs / cover shorts.",
            min(90.0, 60.0 + abs(funding_pct) * 800),
        )
    if funding_pct >= 0.005:
        return (
            InsightStance.HOLD,
            "Funding mildly positive - slight long crowding, but not a clear short yet.",
            58.0,
        )
    if funding_pct <= -0.005:
        return (
            InsightStance.HOLD,
            "Funding mildly negative - slight short crowding, but not a clear long yet.",
            58.0,
        )
    return (
        InsightStance.HOLD,
        "Funding is near flat - no strong directional edge from funding alone.",
        65.0,
    )


def _format_usd_short(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.2f}K"
    return f"${value:.0f}"


def _heuristic_inference(trader: TraderProfile) -> StrategyInference:
    positions = _positions_for_trader(trader.address)
    total_notional = sum(p.size_usd for p in positions)
    avg_lev = sum(p.leverage for p in positions) / len(positions) if positions else 0.0
    top_asset = None
    concentration = 0.0
    if total_notional > 0:
        asset_totals: dict[str, float] = {}
        for pos in positions:
            asset_totals[pos.asset] = asset_totals.get(pos.asset, 0.0) + pos.size_usd
        top_asset, top_size = max(asset_totals.items(), key=lambda item: item[1])
        concentration = top_size / total_notional

    turnover_ratio = 0.0
    if trader.account_value_usd > 0:
        turnover_ratio = trader.volume_usd / trader.account_value_usd

    tags = [t.lower() for t in trader.strategy_tags]
    if avg_lev >= 20:
        strategy, style = "Speculative", "High-leverage trader"
    elif concentration >= 0.8 and total_notional > 0:
        strategy, style = (
            "Directional",
            f"Concentrated {top_asset} exposure" if top_asset else "Concentrated exposure",
        )
    elif len(positions) >= 4:
        strategy, style = "Diversified", "Multi-asset allocator"
    elif turnover_ratio >= 20:
        strategy, style = "Scalping", "High turnover trader"
    elif any("momentum" in t or "breakout" in t for t in tags):
        strategy, style = "Momentum", "Breakout trader"
    elif any("mean" in t or "reversion" in t for t in tags):
        strategy, style = "Mean Reversion", "Counter-trend trader"
    elif any("funding" in t or "arb" in t for t in tags):
        strategy, style = "Funding Arbitrage", "Market-neutral trader"
    elif any("swing" in t for t in tags):
        strategy, style = "Swing Trading", "Multi-day swing trader"
    elif any("trend" in t for t in tags):
        strategy, style = "Trend Following", "Directional trend trader"
    else:
        strategy, style = "Mixed", "Opportunistic trader"

    if trader.risk_score >= 75:
        risk = "Aggressive"
    elif trader.risk_score >= 50:
        risk = "Balanced"
    else:
        risk = "Conservative"

    # Prefer live signals (positions, leverage, PnL/ROI, risk). Win-rate inputs
    # only contribute when collectors actually populate trade stats.
    has_trade_stats = trader.total_trades > 0
    trade_stats_boost = (
        trader.win_rate * 0.5 + min(trader.total_trades, 500) / 500 * 20
        if has_trade_stats
        else min(abs(trader.pnl_change_pct), 80) * 0.25
        + min(abs(trader.pnl_usd) / 1_000_000, 20)
    )
    confidence = min(
        95.0,
        max(
            45.0,
            trade_stats_boost
            + min(avg_lev, 30) / 30 * 10
            + min(len(positions), 5) * 3
            + (100 - abs(trader.risk_score - 60)) * 0.2,
        ),
    )

    assets_label = ", ".join(sorted({p.asset for p in positions})) if positions else "n/a"
    if has_trade_stats:
        stats_line = (
            f"{trader.alias} shows {trader.win_rate:.1f}% win rate across "
            f"{trader.total_trades} trades"
            + (
                f" with avg hold {trader.avg_hold_hours:.1f}h. "
                if trader.avg_hold_hours > 0
                else ". "
            )
        )
    else:
        stats_line = (
            f"{trader.alias} has all-time PnL ${trader.pnl_usd:,.0f} "
            f"({trader.pnl_change_pct:+.1f}% ROI). "
        )
    rationale = (
        f"{stats_line}"
        f"Avg leverage {avg_lev:.1f}x across {len(positions)} open positions "
        f"({assets_label}). Turnover ratio {turnover_ratio:.1f}x supports {strategy.lower()} classification."
    )

    from app.services.market_brief import canonicalize_strategy

    return StrategyInference(
        id=store.new_id("inf"),
        trader_address=trader.address,
        trader_alias=trader.alias,
        strategy=canonicalize_strategy(strategy),
        trading_style=style,
        risk_profile=risk,
        confidence=round(confidence, 1),
        rationale=rationale,
        provider="heuristic",
        created_at=_utcnow(),
    )


async def _llm_inference(trader: TraderProfile, provider: str) -> StrategyInference | None:
    if provider == "openai":
        api_key = settings.openai_api_key
        base_url = settings.openai_base_url
        model = settings.openai_model
    elif provider == "deepseek":
        api_key = settings.deepseek_api_key
        base_url = settings.deepseek_base_url
        model = settings.deepseek_model
    else:
        return None

    if not api_key:
        return None

    positions = _positions_for_trader(trader.address)
    prompt = {
        "trader": trader.alias,
        "win_rate": trader.win_rate,
        "avg_hold_hours": trader.avg_hold_hours,
        "total_trades": trader.total_trades,
        "preferred_assets": trader.preferred_assets,
        "strategy_tags": trader.strategy_tags,
        "risk_score": trader.risk_score,
        "pnl_change_pct": trader.pnl_change_pct,
        "account_value_usd": trader.account_value_usd,
        "volume_usd": trader.volume_usd,
        "open_positions": len(positions),
        "avg_leverage": round(
            sum(p.leverage for p in positions) / len(positions), 2
        )
        if positions
        else 0.0,
        "position_assets": sorted({p.asset for p in positions}),
    }

    system = (
        "You classify Hyperliquid trader strategies. "
        "Respond ONLY with JSON keys: strategy, trading_style, risk_profile, "
        "confidence (0-100), rationale. "
        "strategy MUST be exactly one of: Speculative, Directional, Diversified, "
        "Scalping, Momentum, Mean Reversion, Funding Arbitrage, Swing Trading, "
        "Trend Following, Mixed."
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(prompt)},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            from app.services.market_brief import canonicalize_strategy

            return StrategyInference(
                id=store.new_id("inf"),
                trader_address=trader.address,
                trader_alias=trader.alias,
                strategy=canonicalize_strategy(str(data.get("strategy", "Mixed"))),
                trading_style=str(data.get("trading_style", "Opportunistic trader")),
                risk_profile=str(data.get("risk_profile", "Balanced")),
                confidence=float(data.get("confidence", 60)),
                rationale=str(data.get("rationale", "")),
                provider=provider,
                created_at=_utcnow(),
            )
    except Exception as exc:
        logger.warning("LLM inference failed (%s): %s", provider, exc)
        return None


def _resolve_provider() -> str:
    if settings.ai_provider != "auto":
        return settings.ai_provider
    if settings.has_openai:
        return "openai"
    if settings.has_deepseek:
        return "deepseek"
    return "heuristic"


async def run_inference_pipeline() -> list[StrategyInference]:
    # Desk brief first so trader LLM spend does not starve the Insights hero.
    try:
        from app.services.market_brief import generate_market_brief

        await generate_market_brief()
    except Exception:
        logger.exception("Market brief generation failed")

    provider = _resolve_provider()
    results: list[StrategyInference] = []
    priority_addresses = [a.trader_address for a in store.whale_alerts[:10]]
    limit = max(1, settings.inference_trader_limit, len(priority_addresses))
    priority = [t for t in store.traders if t.address in priority_addresses]
    remainder = [t for t in store.traders if t.address not in priority_addresses]
    traders = (priority + remainder)[:limit]

    for trader in traders:
        item: StrategyInference | None = None
        if provider in {"openai", "deepseek"}:
            item = await _llm_inference(trader, provider)
        if item is None:
            item = _heuristic_inference(trader)
            item.provider = "heuristic" if provider == "heuristic" else f"{provider}-fallback"

        results.append(item)
        store.persist_inference(item)

    with store._lock:
        store.inferences = results + [
            i for i in store.inferences if i.trader_address not in {r.trader_address for r in results}
        ]
        store.last_inference_at = _utcnow()
        store.ai_provider = results[0].provider if results else provider

    store.refresh_dashboard()
    _build_market_insights()
    return results


def _whale_bias_vote(long_pct: float) -> tuple[InsightStance, str]:
    if long_pct >= 58:
        return InsightStance.BUY, f"Whales {long_pct:.0f}% long"
    if long_pct <= 42:
        return InsightStance.SELL, f"Whales {long_pct:.0f}% long ({100 - long_pct:.0f}% short)"
    return InsightStance.HOLD, f"Whales balanced ({long_pct:.0f}% long)"


def _liq_skew_vote(liq_long: int, liq_short: int) -> tuple[InsightStance, str] | None:
    total = liq_long + liq_short
    if total < 3:
        return None
    # More long liquidations → downside cascade pressure → prefer shorts.
    # More short liquidations → squeeze risk up → prefer longs.
    if liq_long >= liq_short * 1.5 and liq_long >= 3:
        return InsightStance.SELL, f"Liq 24h {liq_long}L / {liq_short}S (long flush)"
    if liq_short >= liq_long * 1.5 and liq_short >= 3:
        return InsightStance.BUY, f"Liq 24h {liq_long}L / {liq_short}S (short flush)"
    return InsightStance.HOLD, f"Liq 24h {liq_long}L / {liq_short}S (mixed)"


def _combine_stance_votes(
    votes: list[InsightStance],
) -> InsightStance:
    score = 0
    for vote in votes:
        if vote == InsightStance.BUY:
            score += 1
        elif vote == InsightStance.SELL:
            score -= 1
    if score >= 2:
        return InsightStance.BUY
    if score <= -2:
        return InsightStance.SELL
    if score > 0:
        return InsightStance.BUY
    if score < 0:
        return InsightStance.SELL
    return InsightStance.HOLD


def _latest_snapshots_by_asset(assets: list[str]) -> dict[str, MarketSnapshotRow]:
    if not assets:
        return {}
    db = SessionLocal()
    try:
        out: dict[str, MarketSnapshotRow] = {}
        for asset in assets:
            row = (
                db.query(MarketSnapshotRow)
                .filter(MarketSnapshotRow.asset == asset)
                .order_by(MarketSnapshotRow.timestamp.desc())
                .first()
            )
            if row:
                out[asset] = row
        return out
    finally:
        db.close()


def _build_coin_stance_insights(now: datetime) -> list[MarketInsight]:
    """BL-02: per-coin actionable stance from whale bias + funding + liq skew.

    Only emit a card when at least two signal families are available so the
    call is more than a single-metric echo of the whale book panel.
    """
    summary = store.whale_summary
    if not summary or not summary.by_asset:
        return []

    ranked = sorted(
        summary.by_asset.values(),
        key=lambda a: a.long_notional_usd + a.short_notional_usd,
        reverse=True,
    )[:5]
    assets = [a.asset for a in ranked]
    snapshots = _latest_snapshots_by_asset(assets)

    cutoff = now - timedelta(hours=24)
    liq_counts: dict[str, dict[str, int]] = {}
    for event in store.liquidation_events:
        if event.timestamp < cutoff:
            continue
        bucket = liq_counts.setdefault(event.asset, {"long": 0, "short": 0})
        key = "long" if event.side.value == "long" else "short"
        bucket[key] += 1

    cards: list[MarketInsight] = []
    for asset_summary in ranked:
        if len(cards) >= 3:
            break
        asset = asset_summary.asset
        votes: list[InsightStance] = []
        signal_labels: list[str] = []
        reason_bits: list[str] = []

        whale_stance, whale_label = _whale_bias_vote(asset_summary.long_pct)
        votes.append(whale_stance)
        signal_labels.append(
            f"Whale L/S: {asset_summary.long_pct:.0f}% / "
            f"{max(0.0, 100.0 - asset_summary.long_pct):.0f}%"
        )
        reason_bits.append(whale_label)

        snapshot = snapshots.get(asset)
        if snapshot is not None:
            funding_pct = float(snapshot.funding_rate) * 100.0
            fund_stance, fund_reason, _ = _funding_stance(funding_pct)
            votes.append(fund_stance)
            signal_labels.append(f"Funding: {funding_pct:+.3f}%")
            reason_bits.append(fund_reason.rstrip("."))

        liq = liq_counts.get(asset, {"long": 0, "short": 0})
        liq_vote = _liq_skew_vote(liq["long"], liq["short"])
        if liq_vote is not None:
            liq_stance, liq_label = liq_vote
            votes.append(liq_stance)
            signal_labels.append(f"Liq 24h: {liq['long']}L / {liq['short']}S")
            reason_bits.append(liq_label)

        # Need whale + at least one other family (funding and/or liq).
        if len(votes) < 2:
            continue

        stance = _combine_stance_votes(votes)
        agree = sum(1 for v in votes if v == stance)
        confidence = min(92.0, 55.0 + agree * 12.0 + min(15.0, asset_summary.whales))
        net_label = _format_usd_short(abs(asset_summary.net_notional_usd))
        net_side = "long" if asset_summary.net_notional_usd >= 0 else "short"
        action = {
            InsightStance.BUY: "Prefer longs",
            InsightStance.SELL: "Prefer shorts",
            InsightStance.HOLD: "No clear direction — wait",
        }[stance]

        cards.append(
            MarketInsight(
                id=store.new_id("mi"),
                title=f"{asset}: {stance.value.upper()} - whale book",
                summary=(
                    f"{action}. {'; '.join(reason_bits)}. "
                    f"Net whale {net_side} {net_label} across {asset_summary.whales} wallets."
                ),
                asset=asset,
                stance=stance,
                confidence=round(confidence, 1),
                signals=[
                    f"Action: {stance.value.upper()}",
                    *signal_labels[:3],
                ],
                created_at=now,
            )
        )
    return cards


# BL-11 extreme-funding filter: only liquid coins (top-N by 24h volume) AND
# an extreme |funding| can trigger the callout, so one thin alt (e.g. STX)
# can't dominate. Threshold is 2x the "crowded" level in _funding_stance.
FUNDING_LIQUID_TOP_N = 20
FUNDING_EXTREME_ABS_PCT = 0.02


def _build_funding_crowdedness_insight(now: datetime) -> list[MarketInsight]:
    """BL-11: extreme funding among liquid coins (top-N volume ∩ |funding| ≥ threshold).

    Extreme funding flags possible local tops/bottoms: heavily positive means
    longs are crowded (top / long-flush risk), heavily negative means shorts
    are crowded (bottom / short-squeeze risk). No callout when nothing is extreme.
    """
    ticks = store.market_ticks or {}
    rows: list[tuple[str, float, float]] = []
    for asset, tick in ticks.items():
        rate = tick.get("funding_rate")
        if rate is None:
            continue
        try:
            funding_pct = float(rate) * 100.0
            volume_usd = float(tick.get("day_volume_usd") or 0.0)
        except (TypeError, ValueError):
            continue
        rows.append((str(asset), funding_pct, volume_usd))

    if not rows:
        return []

    rows.sort(key=lambda item: item[2], reverse=True)
    liquid = rows[:FUNDING_LIQUID_TOP_N]
    extreme = [
        row for row in liquid if abs(row[1]) >= FUNDING_EXTREME_ABS_PCT
    ]
    if not extreme:
        return []

    extreme.sort(key=lambda item: abs(item[1]), reverse=True)
    top = extreme[:3]

    signal_labels: list[str] = []
    summary_bits: list[str] = []
    for asset, funding_pct, _ in top:
        if funding_pct >= 0:
            pay = "longs pay shorts — longs crowded"
        else:
            pay = "shorts pay longs — shorts crowded"
        signal_labels.append(f"{asset} funding {funding_pct:+.4f}% ({pay})")
        summary_bits.append(f"{asset} funding {funding_pct:+.4f}% ({pay})")

    top_asset, top_pct, _ = top[0]
    hint = (
        "Possible local top / long-flush risk."
        if top_pct >= 0
        else "Possible local bottom / short-squeeze risk."
    )
    stance, reason, conf = _funding_stance(top_pct)
    return [
        MarketInsight(
            id=store.new_id("mi"),
            title="Extreme funding",
            summary=(
                f"{reason} {hint} "
                f"Extreme among top-{FUNDING_LIQUID_TOP_N} volume coins: "
                f"{', '.join(summary_bits)}."
            ),
            asset=top_asset,
            stance=stance,
            confidence=round(min(88.0, conf), 1),
            signals=[
                f"Action: {stance.value.upper()}",
                *signal_labels,
            ],
            created_at=now,
        )
    ]


def _build_market_insights() -> None:
    insights: list[MarketInsight] = []
    now = _utcnow()

    # BL-02 primary: multi-signal per-coin stance cards (max 3).
    coin_cards = _build_coin_stance_insights(now)
    insights.extend(coin_cards)
    # BL-11: cross-market extreme funding callout.
    funding_cards = _build_funding_crowdedness_insight(now)
    insights.extend(funding_cards)

    # Top3 volume whale consensus — evidence card (not a Dashboard KPI clone).
    try:
        from app.services.alerts import compute_market_consensus

        computed = compute_market_consensus()
        if computed:
            mood, reason, long_pct = computed
            if "BULL" in mood:
                c_stance = InsightStance.BUY
                action = "Prefer longs"
            elif "BEAR" in mood:
                c_stance = InsightStance.SELL
                action = "Prefer shorts"
            else:
                c_stance = InsightStance.HOLD
                action = "Wait"
            insights.append(
                MarketInsight(
                    id=store.new_id("mi"),
                    title=f"Top3 Consensus · {mood}",
                    summary=f"{action}. {reason}",
                    stance=c_stance,
                    confidence=min(88.0, 55.0 + abs(50.0 - long_pct) * 0.6),
                    signals=[
                        f"Action: {c_stance.value.upper()}",
                        f"Long share: {long_pct:.0f}%",
                        f"Mood: {mood}",
                    ],
                    created_at=now,
                )
            )
    except Exception:
        logger.exception("Top3 consensus insight failed")

    if store.whale_summary and store.whale_summary.with_positions > 0:
        summary = store.whale_summary
        net_label = _format_usd_short(abs(summary.net_notional_usd))
        direction = summary.net_bias.upper()
        if summary.long_pct >= 58:
            whale_stance = InsightStance.BUY
            whale_action = "Whales are net long: prefer longs."
        elif summary.long_pct <= 42:
            whale_stance = InsightStance.SELL
            whale_action = "Whales are net short: prefer shorts."
        else:
            whale_stance = InsightStance.HOLD
            whale_action = "Whale long/short split is balanced - no clean directional call."
        insights.append(
            MarketInsight(
                id=store.new_id("mi"),
                title=f"Book-wide: whales net {direction}",
                summary=(
                    f"{whale_action} "
                    f"{summary.with_positions}/{summary.tracked} whales positioned; "
                    f"long {_format_usd_short(summary.long_notional_usd)} "
                    f"({summary.long_pct:.0f}%) vs short {_format_usd_short(summary.short_notional_usd)}."
                ),
                stance=whale_stance,
                confidence=72.0,
                signals=[
                    f"Action: {whale_stance.value.upper()}",
                    f"Long share: {summary.long_pct:.0f}%",
                    f"Net: {direction} ({net_label})",
                ],
                created_at=now,
            )
        )

    entry_cutoff = now - timedelta(hours=24)
    entries: dict[str, dict[str, float]] = {}
    entry_counts: dict[str, dict[str, int]] = {}
    for alert in store.whale_alerts:
        if alert.timestamp < entry_cutoff:
            continue
        if alert.alert_type.value != "entry":
            continue
        bucket = entries.setdefault(alert.asset, {"long": 0.0, "short": 0.0})
        counts = entry_counts.setdefault(alert.asset, {"long": 0, "short": 0})
        key = "long" if alert.side.value == "long" else "short"
        bucket[key] += alert.size_usd
        counts[key] += 1

    covered = {i.asset for i in insights if i.asset}
    if entries:
        asset, totals = max(entries.items(), key=lambda item: item[1]["long"] + item[1]["short"])
        if asset not in covered:
            counts = entry_counts.get(asset, {"long": 0, "short": 0})
            bias = "long" if totals["long"] >= totals["short"] else "short"
            entry_stance = InsightStance.BUY if bias == "long" else InsightStance.SELL
            insights.append(
                MarketInsight(
                    id=store.new_id("mi"),
                    title=f"Fresh {asset} {bias} entries",
                    summary=(
                        f"{'Prefer longs' if entry_stance == InsightStance.BUY else 'Prefer shorts'} on {asset}: "
                        f"{counts['long']} long vs {counts['short']} short whale entries in 24h "
                        f"({_format_usd_short(totals['long'])} vs {_format_usd_short(totals['short'])})."
                    ),
                    asset=asset,
                    stance=entry_stance,
                    confidence=70.0,
                    signals=[
                        f"Action: {entry_stance.value.upper()}",
                        f"Entries: {counts['long']}L / {counts['short']}S",
                        f"Long size: {_format_usd_short(totals['long'])}",
                    ],
                    created_at=now,
                )
            )

    if store.liquidation_zones:
        largest = max(store.liquidation_zones, key=lambda z: z.size_usd)
        liq_cutoff = now - timedelta(hours=24)
        liq_long = len(
            [
                e
                for e in store.liquidation_events
                if e.asset == largest.asset
                and e.side.value == "long"
                and e.timestamp >= liq_cutoff
            ]
        )
        liq_short = len(
            [
                e
                for e in store.liquidation_events
                if e.asset == largest.asset
                and e.side.value == "short"
                and e.timestamp >= liq_cutoff
            ]
        )
        if largest.side.value == "long":
            liq_stance = InsightStance.SELL
            liq_action = (
                f"Prefer shorts — cut or avoid longs: large LONG liquidation magnet at "
                f"${largest.price:,.0f}."
            )
        else:
            liq_stance = InsightStance.BUY
            liq_action = (
                f"Prefer longs — cut or avoid shorts: large SHORT liquidation magnet at "
                f"${largest.price:,.0f}."
            )
        if abs(largest.distance_pct) > 8:
            liq_stance = InsightStance.HOLD
            liq_action = (
                f"HOLD for now - nearest {largest.side.value.upper()} liq cluster "
                f"(${largest.price:,.0f}) is still {largest.distance_pct:+.1f}% away."
            )
        insights.append(
            MarketInsight(
                id=store.new_id("mi"),
                title=f"{largest.asset} liquidation cluster risk",
                summary=(
                    f"{liq_action} Zone size ${largest.size_usd / 1_000_000:.0f}M "
                    f"({largest.open_interest_pct:.1f}% of OI)."
                ),
                asset=largest.asset,
                stance=liq_stance,
                confidence=min(95.0, 50 + largest.open_interest_pct * 1.5),
                signals=[
                    f"Action: {liq_stance.value.upper()}",
                    f"Distance: {largest.distance_pct:+.1f}%",
                    f"Liq 24h: {liq_long}L / {liq_short}S",
                ],
                created_at=now,
            )
        )

    try:
        windows = rollup_liq_windows(now)
        w1 = windows.get("1h") or {}
        w4 = windows.get("4h") or {}
        pick_key = "1h" if float(w1.get("total_usd") or 0) > 0 else "4h"
        pick = w1 if pick_key == "1h" else w4
        line = pressure_line(pick)
        if line != "sampled liq quiet":
            if "long-flush" in line:
                liq_w_stance = InsightStance.SELL
                liq_w_action = "Prefer shorts — longs are being flushed."
            elif "short-flush" in line:
                liq_w_stance = InsightStance.BUY
                liq_w_action = "Prefer longs — shorts are being flushed."
            else:
                liq_w_stance = InsightStance.HOLD
                liq_w_action = "Wait — sampled liq is two-sided."
            insights.append(
                MarketInsight(
                    id=store.new_id("mi"),
                    title=f"Liq pressure · {pick_key}",
                    summary=(
                        f"{liq_w_action} {pick_key} sampled "
                        f"L {_format_usd_short(float(pick.get('long_usd') or 0))} vs "
                        f"S {_format_usd_short(float(pick.get('short_usd') or 0))} "
                        f"({int(pick.get('events') or 0)} events)."
                    ),
                    stance=liq_w_stance,
                    confidence=68.0,
                    signals=[
                        f"Action: {liq_w_stance.value.upper()}",
                        f"Window: {pick_key}",
                        f"Pressure: {line}",
                    ],
                    created_at=now,
                )
            )
    except Exception:
        logger.exception("Liq window insight failed")

    def _priority(card: MarketInsight) -> tuple[int, float]:
        title = card.title.lower()
        if card.asset and "whale book" in title:
            return (0, -card.confidence)
        if title.startswith("extreme funding"):
            return (1, -card.confidence)
        if title.startswith("top3 consensus"):
            return (2, -card.confidence)
        if "liquidation cluster" in title:
            return (3, -card.confidence)
        if title.startswith("liq pressure"):
            return (3, -card.confidence)
        return (4, -card.confidence)

    insights.sort(key=_priority)
    with store._lock:
        store.insights = insights[:8]


def apply_inference_to_alerts(alerts: list[WhaleAlert]) -> list[WhaleAlert]:
    updated: list[WhaleAlert] = []
    for alert in alerts:
        inference = store.get_inference(alert.trader_address)
        if inference:
            alert = alert.model_copy(
                update={
                    "inferred_strategy": inference.strategy,
                    "confidence_score": inference.confidence,
                }
            )
        else:
            positions = _positions_for_trader(alert.trader_address)
            avg_lev = sum(p.leverage for p in positions) / len(positions) if positions else 0.0
            if avg_lev >= 20:
                fallback = "Speculative"
            elif len(positions) == 1:
                fallback = "Directional"
            elif len(positions) >= 4:
                fallback = "Diversified"
            else:
                fallback = "Mixed"
            alert = alert.model_copy(
                update={
                    "inferred_strategy": fallback,
                    "confidence_score": max(55.0, alert.confidence_score),
                }
            )
        updated.append(alert)
    return updated


def enrich_rankings_with_inference() -> None:
    """Attach latest inference strategy and refresh open ROI on ranking rows."""
    if not store.rankings:
        return
    inference_map = {
        item.trader_address.lower(): item.strategy for item in store.inferences
    }
    # Compute outside the lock — summarize_open_pnl hits the DB.
    refreshed: list[SmartMoneyRank] = []
    for rank in list(store.rankings):
        open_roi_pct, open_unrealized_pnl_usd = store.summarize_open_pnl(rank.address)
        refreshed.append(
            rank.model_copy(
                update={
                    "inferred_strategy": inference_map.get(
                        rank.address.lower(), rank.inferred_strategy
                    ),
                    "open_roi_pct": open_roi_pct,
                    "open_unrealized_pnl_usd": open_unrealized_pnl_usd,
                }
            )
        )
    with store._lock:
        store.rankings = refreshed
