"""Compare published brief inputs without consulting the current market."""
from datetime import datetime, timedelta, timezone
from math import isfinite

LIMITS = {"mark": 1.0, "funding": 0.01, "whale_long_share": 5.0}
MAX_AGE = timedelta(minutes=45)


def _fresh(value, at):
    try:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timedelta(0) <= at - timestamp < MAX_AGE
    except (TypeError, ValueError):
        return False


def _number(value):
    return value if type(value) in (float, int) and isfinite(value) else None


def _wallets(evidence, asset):
    return {p["trader_address"].lower() for p in evidence["context"].get("positions", [])
            if p.get("asset") == asset and p.get("trader_address")}


def compare_briefs(current: dict, previous: dict | None, at: datetime,
                   previous_at: datetime | None) -> dict:
    if previous is None or previous_at is None:
        return {"status": "no_baseline", "changes": []}
    new, old = current["inputs"], previous["inputs"]
    new_book, old_book = new.get("top3_consensus", {}), old.get("top3_consensus", {})
    assets, prior_assets = set(new_book.get("assets", [])), set(old_book.get("assets", []))
    partial = assets != prior_assets
    candidates = []
    comparable = 0

    def add(asset, metric, before, after):
        nonlocal comparable, partial
        before, after = _number(before), _number(after)
        if before is None or after is None or (metric == "mark" and min(before, after) <= 0):
            partial = True
            return
        comparable += 1
        delta = round((after / before - 1) * 100 if metric == "mark" else after - before, 6)
        if abs(delta) >= LIMITS[metric]:
            candidates.append({"asset": asset, "metric": metric, "delta": delta})

    for asset in sorted(assets & prior_assets):
        a, b = new.get("tape", {}).get(asset, {}), old.get("tape", {}).get(asset, {})
        if _fresh(a.get("updated_at"), at) and _fresh(b.get("updated_at"), previous_at):
            add(asset, "mark", b.get("mark_price"), a.get("mark_price"))
            add(asset, "funding", b.get("funding_pct"), a.get("funding_pct"))
        else:
            partial = True

        wallets = _wallets(current, asset)
        if (wallets and wallets == _wallets(previous, asset)
                and _fresh(new.get("book_updated_at"), at)
                and _fresh(old.get("book_updated_at"), previous_at)):
            def share(book):
                return next((r.get("long_pct") for r in book.get("per_asset", [])
                             if r.get("asset") == asset), None)
            add(asset, "whale_long_share", share(old_book), share(new_book))
        else:
            partial = True
    candidates.sort(key=lambda c: (-abs(c["delta"]) / LIMITS[c["metric"]], c["asset"], c["metric"]))
    status = "unavailable" if not comparable else "partial" if partial else "changed" if candidates else "unchanged"
    return {"status": status, "changes": candidates[:2]}
