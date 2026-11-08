"""Append-only, content-addressed signal inputs and emitted decisions."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone

from app.db import SessionLocal
from app.config import settings
from app.models.orm import EvidenceRow, WhaleFlowRow
from app.services.store import store


def capture_context() -> dict:
    from app.services.ranking import select_smart_money_ranks
    from app.services.verified_liquidations import summary
    with store._lock:
        smart = {r.address.lower(): r.rank for r in select_smart_money_ranks()}
        context = {
            "scope": "tracked_wallets",
            "rank_policy": "size-selected cohort sorted by smart_money_score; not a trade recommendation",
            "rankings": [{**r.model_dump(mode="json"), "smart_money_rank": smart.get(r.address.lower())} for r in store.rankings],
            "size_ranks": [{"address": t.address, "size_rank": t.rank} for t in store.traders],
            "positions": [p.model_dump(mode="json") for p in store.whale_positions],
            "wallet_observed_at": dict(store.whale_observed_at),
            "whale_alerts": [a.model_dump(mode="json") for a in store.whale_alerts],
            "liquidation_zones": [z.model_dump(mode="json") for z in store.liquidation_zones],
            "liquidation_events": [e.model_dump(mode="json") for e in store.liquidation_events] if settings.use_mock_data else [],
            "market": copy.deepcopy(store.market_ticks),
            "collectors": {k: v.model_dump(mode="json") for k, v in store.collectors.items()},
            "book": store.whale_summary.model_dump(mode="json") if store.whale_summary else None,
        }
    context["liquidation_coverage"] = summary()
    with SessionLocal() as db:
        from datetime import timedelta
        rows = db.query(WhaleFlowRow).filter(WhaleFlowRow.created_at >= datetime.now(timezone.utc) - timedelta(hours=1)).all()
        context["flows"] = [{"wallet": r.trader_address, "asset": r.asset, "previous_usd": r.previous_usd,
                             "current_usd": r.current_usd, "delta_usd": r.delta_usd, "as_of": r.created_at,
                             "previous_as_of": r.previous_at,
                             "source": "snapshot_delta_not_fill"} for r in rows]
    return context


def envelope(kind: str, inputs: dict, outputs: dict | list, *, context: dict | None = None) -> tuple[str, str]:
    body = {"schema_version": 1, "engine_version": f"{kind}_v1", "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs,
            "context": context if context is not None else capture_context(), "outputs": outputs}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest(), raw


def save(db, evidence: tuple[str, str]) -> str:
    key, raw = evidence
    if db.get(EvidenceRow, key) is None:
        db.add(EvidenceRow(id=key, body=raw))
    return key


def retrieve(key: str) -> dict | None:
    with SessionLocal() as db:
        row = db.get(EvidenceRow, key)
        if row is None:
            return None
        if hashlib.sha256(row.body.encode()).hexdigest() != key:
            raise ValueError("Evidence digest mismatch")
        return {"id": key, **json.loads(row.body)}
