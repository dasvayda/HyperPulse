import asyncio

from app.config import settings
from app.services import alerts


def test_telegram_send_retries_until_success(monkeypatch) -> None:
    attempts: list[str] = []

    async def flaky_once(message: str) -> bool:
        attempts.append(message)
        return len(attempts) == 3

    monkeypatch.setattr(alerts, "_send_telegram_once", flaky_once)
    monkeypatch.setattr(settings, "telegram_send_attempts", 3)
    monkeypatch.setattr(settings, "telegram_retry_delay_seconds", 0)

    assert asyncio.run(alerts._send_telegram("test")) is True
    assert attempts == ["test", "test", "test"]


def test_telegram_send_stops_after_configured_attempts(monkeypatch) -> None:
    attempts: list[str] = []

    async def always_fail(message: str) -> bool:
        attempts.append(message)
        return False

    monkeypatch.setattr(alerts, "_send_telegram_once", always_fail)
    monkeypatch.setattr(settings, "telegram_send_attempts", 2)
    monkeypatch.setattr(settings, "telegram_retry_delay_seconds", 0)

    assert asyncio.run(alerts._send_telegram("test")) is False
    assert attempts == ["test", "test"]
