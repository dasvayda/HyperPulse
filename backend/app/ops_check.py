"""Read-only operator check. Never imports DB/settings or triggers pipeline work."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

ENDPOINTS = {
    "liveness": "/health",
    "readiness": "/health/ready",
    "pipeline": "/api/v2/pipeline/status",
    "telegram": "/api/v2/alerts/summary",
}
REQUIRED_STAGES = {"collector", "trader_refresh", "inference", "ranking", "alerts"}


def origin(value: str) -> str:
    try:
        url = urlsplit(value)
        valid = (url.scheme in {"http", "https"} and url.hostname and not url.username
                 and not url.password and url.path in {"", "/"} and not url.query
                 and not url.fragment and (url.port is None or 0 < url.port <= 65535))
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("Use an HTTP(S) origin without credentials, path, query or fragment")
    return value.rstrip("/")


def positive_seconds(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("Seconds must be finite and positive")
    return result


def check_service(client: httpx.Client, base_url: str, *, max_stage_age: float = 600,
                  now: datetime | None = None) -> dict:
    base_url = origin(base_url)
    checked_at = now or datetime.now(timezone.utc)
    checks: dict = {}
    issues: list[dict] = []
    payloads: dict = {}

    def issue(level: int, code: str) -> None:
        issues.append({"level": level, "code": code})

    for name, path in ENDPOINTS.items():
        try:
            response = client.get(base_url + path)
            checks[name] = {"http_status": response.status_code}
            if response.status_code != 200:
                issue(2, f"{name}_http_error")
                continue
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object")
            payloads[name] = body
        except (httpx.HTTPError, ValueError):
            # No raw URL, response body, provider exception or settings in output.
            checks[name] = {"error": "unavailable_or_invalid_json"}
            issue(2, f"{name}_unavailable")

    if "liveness" in payloads and payloads["liveness"].get("status") != "ok":
        issue(2, "liveness_not_ok")
    readiness = payloads.get("readiness")
    if readiness is not None:
        if readiness.get("status") != "ready":
            issue(2, "service_not_ready")
        for name in ("database", "collector"):
            if not isinstance(readiness.get(name), dict) or readiness[name].get("status") != "ok":
                issue(2, f"{name}_not_ready")
        cache = readiness.get("cache", {})
        if not isinstance(cache, dict) or cache.get("status") not in {"ok", "fallback"}:
            issue(2, "cache_unavailable")
        elif cache["status"] == "fallback":
            issue(1, "cache_memory_fallback")

    pipeline = payloads.get("pipeline")
    if pipeline is not None:
        stages = pipeline.get("stages")
        if not isinstance(stages, dict) or not REQUIRED_STAGES.issubset(stages):
            issue(2, "pipeline_stage_status_missing")
        else:
            for name in sorted(REQUIRED_STAGES):
                stage = stages[name]
                if not isinstance(stage, dict):
                    issue(2, f"{name}_invalid_stage")
                    continue
                status = stage.get("status")
                if status in {"error", "degraded"}:
                    issue(2, f"{name}_{status}")
                elif status in {"never_run", "cancelled"}:
                    issue(1, f"{name}_{status}")
                elif status in {"ok", "running"}:
                    time_field = "started_at" if status == "running" else "last_success_at"
                    try:
                        timestamp = datetime.fromisoformat(stage[time_field].replace("Z", "+00:00"))
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        age = (checked_at - timestamp).total_seconds()
                        # Leaderboard refresh legitimately runs on a 15m cadence.
                        age_limit = max(max_stage_age, 1800) if name == "trader_refresh" and status == "ok" else max_stage_age
                        if age > age_limit or age < -60:
                            issue(2, f"{name}_stale_or_clock_skew")
                    except (KeyError, TypeError, AttributeError, ValueError):
                        issue(2, f"{name}_time_invalid")
                else:
                    issue(2, f"{name}_status_unknown")

    telegram = payloads.get("telegram")
    if telegram is not None:
        for name in ("sent", "failed", "queued", "attempted"):
            value = telegram.get(name)
            if type(value) is not int or value < 0:
                issue(2, "telegram_counts_invalid")
                break
        else:
            if telegram["attempted"] != telegram["sent"] + telegram["failed"]:
                issue(2, "telegram_counts_inconsistent")
            if telegram["failed"]:
                issue(1, "telegram_failures_last_24h")
            if telegram["queued"]:
                issue(1, "telegram_queued_last_24h")
        if not pipeline or not pipeline.get("telegram_configured"):
            issue(1, "telegram_not_configured")
    level = max((item["level"] for item in issues), default=0)
    return {"status": ("ok", "warning", "critical")[level], "exit_code": level,
            "checked_at": checked_at.isoformat(), "checks": checks, "issues": issues}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", type=origin, default="http://127.0.0.1:8100")
    parser.add_argument("--timeout", type=positive_seconds, default=5.0)
    parser.add_argument("--max-stage-age", type=positive_seconds, default=600.0)
    args = parser.parse_args(argv)
    with httpx.Client(timeout=args.timeout, follow_redirects=False, trust_env=False) as client:
        result = check_service(client, args.base_url, max_stage_age=args.max_stage_age)
    print(json.dumps(result, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
