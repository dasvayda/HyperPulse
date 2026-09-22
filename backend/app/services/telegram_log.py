"""Rolling log of recent Telegram alert bodies (for copy tuning)."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR

logger = logging.getLogger(__name__)

LOG_DIR = BACKEND_DIR / "logs"
LOG_PATH = LOG_DIR / "telegram_recent.json"
MAX_ENTRIES = 20
_lock = threading.Lock()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_telegram_log(
    *,
    event_type: str,
    title: str,
    message_html: str,
    message_plain: str,
    status: str,
) -> None:
    """Prepend one outbound Telegram payload; keep only the newest MAX_ENTRIES."""
    entry: dict[str, Any] = {
        "at": _utcnow_iso(),
        "event_type": event_type,
        "title": title,
        "status": status,
        "message_plain": message_plain,
        "message_html": message_html,
    }
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _lock:
            rows: list[dict[str, Any]] = []
            if LOG_PATH.exists():
                try:
                    raw = json.loads(LOG_PATH.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        rows = [r for r in raw if isinstance(r, dict)]
                except Exception as exc:
                    logger.warning("telegram log read failed: %s", exc)
            rows.insert(0, entry)
            rows = rows[:MAX_ENTRIES]
            LOG_PATH.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except Exception as exc:
        logger.warning("telegram log write failed: %s", exc)
