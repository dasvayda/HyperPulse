from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.models.schemas import MarketInsight, StrategyInference, TraderProfile, WhaleAlert
from app.services.store import store

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _heuristic_inference(trader: TraderProfile) -> StrategyInference:
    tags = [t.lower() for t in trader.strategy_tags]
    if any("momentum" in t or "breakout" in t for t in tags):
        strategy, style = "Momentum", "Breakout trader"
    elif any("mean" in t or "reversion" in t for t in tags):
        strategy, style = "Mean Reversion", "Counter-trend trader"
    elif any("scalp" in t or "high frequency" in t for t in tags):
        strategy, style = "Scalping", "High-frequency trader"
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

    confidence = min(
        95.0,
        max(
            45.0,
            trader.win_rate * 0.55
            + min(trader.total_trades, 500) / 500 * 20
            + (100 - abs(trader.risk_score - 60)) * 0.2,
        ),
    )

    rationale = (
        f"{trader.alias} shows {trader.win_rate:.1f}% win rate across "
        f"{trader.total_trades} trades with avg hold {trader.avg_hold_hours:.1f}h. "
        f"Preferred assets: {', '.join(trader.preferred_assets)}. "
        f"PnL momentum {trader.pnl_change_pct:+.1f}% supports {strategy.lower()} classification."
    )

    return StrategyInference(
        id=store.new_id("inf"),
        trader_address=trader.address,
        trader_alias=trader.alias,
        strategy=strategy,
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

    prompt = {
        "trader": trader.alias,
        "win_rate": trader.win_rate,
        "avg_hold_hours": trader.avg_hold_hours,
        "total_trades": trader.total_trades,
        "preferred_assets": trader.preferred_assets,
        "strategy_tags": trader.strategy_tags,
        "risk_score": trader.risk_score,
        "pnl_change_pct": trader.pnl_change_pct,
    }

    system = (
        "You classify Hyperliquid trader strategies. "
        "Respond ONLY with JSON keys: strategy, trading_style, risk_profile, "
        "confidence (0-100), rationale."
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
            return StrategyInference(
                id=store.new_id("inf"),
                trader_address=trader.address,
                trader_alias=trader.alias,
                strategy=str(data.get("strategy", "Mixed")),
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
    provider = _resolve_provider()
    results: list[StrategyInference] = []
    limit = max(1, settings.inference_trader_limit)
    traders = store.traders[:limit]

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


def _build_market_insights() -> None:
    insights: list[MarketInsight] = []
    now = _utcnow()

    if store.inferences:
        strategies: dict[str, list[StrategyInference]] = {}
        for item in store.inferences:
            strategies.setdefault(item.strategy, []).append(item)
        top_strategy, items = max(strategies.items(), key=lambda kv: len(kv[1]))
        avg_conf = sum(i.confidence for i in items) / len(items)
        insights.append(
            MarketInsight(
                id=store.new_id("mi"),
                title=f"Smart money leaning {top_strategy}",
                summary=(
                    f"{len(items)} tracked whales classified as {top_strategy} "
                    f"with average confidence {avg_conf:.0f}%."
                ),
                confidence=round(avg_conf, 1),
                signals=[
                    f"Dominant strategy: {top_strategy}",
                    f"Tracked traders: {len(store.traders)}",
                    f"Provider: {store.ai_provider}",
                ],
                created_at=now,
            )
        )

    if store.liquidation_zones:
        largest = max(store.liquidation_zones, key=lambda z: z.size_usd)
        insights.append(
            MarketInsight(
                id=store.new_id("mi"),
                title=f"{largest.asset} liquidation cluster risk",
                summary=(
                    f"{largest.side.value.upper()} liquidation zone at "
                    f"${largest.price:,.0f} totaling ${largest.size_usd / 1_000_000:.0f}M."
                ),
                asset=largest.asset,
                confidence=min(95.0, 50 + largest.open_interest_pct * 1.5),
                signals=[
                    f"Distance: {largest.distance_pct:+.1f}%",
                    f"OI share: {largest.open_interest_pct:.1f}%",
                    f"Side: {largest.side.value}",
                ],
                created_at=now,
            )
        )

    if store.whale_alerts:
        recent = store.whale_alerts[0]
        insights.append(
            MarketInsight(
                id=store.new_id("mi"),
                title=f"Whale {recent.alert_type.value} on {recent.asset}",
                summary=(
                    f"{recent.trader_alias} {recent.side.value} {recent.alert_type.value} "
                    f"sized ${recent.size_usd / 1_000_000:.2f}M with "
                    f"{recent.confidence_score:.0f}% confidence."
                ),
                asset=recent.asset,
                confidence=recent.confidence_score,
                signals=[
                    f"Strategy: {recent.inferred_strategy}",
                    f"Leverage: {recent.leverage}x",
                    f"Win rate: {recent.win_rate}%",
                ],
                created_at=now,
            )
        )

    with store._lock:
        store.insights = insights


def apply_inference_to_alerts(alerts: list[WhaleAlert]) -> list[WhaleAlert]:
    inference_map = {i.trader_address: i for i in store.inferences}
    updated: list[WhaleAlert] = []
    for alert in alerts:
        inference = inference_map.get(alert.trader_address)
        if inference:
            alert = alert.model_copy(
                update={
                    "inferred_strategy": inference.strategy,
                    "confidence_score": inference.confidence,
                }
            )
        updated.append(alert)
    return updated
