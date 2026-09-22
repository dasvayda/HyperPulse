from __future__ import annotations

import json
from pathlib import Path

from app.services import telegram_log


def test_append_telegram_log_keeps_last_20(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "telegram_recent.json"
    monkeypatch.setattr(telegram_log, "LOG_DIR", tmp_path)
    monkeypatch.setattr(telegram_log, "LOG_PATH", log_path)

    for i in range(25):
        telegram_log.append_telegram_log(
            event_type="test",
            title=f"t{i}",
            message_html=f"<b>{i}</b>",
            message_plain=str(i),
            status="sent",
        )

    rows = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(rows) == 20
    assert rows[0]["title"] == "t24"
    assert rows[-1]["title"] == "t5"
