import asyncio

import httpx
import pytest
import redis

from app.config import settings
from app.services import telegram_log


def test_default_suite_cannot_contact_live_redis():
    with pytest.raises(ConnectionError, match="disabled in tests"):
        redis.from_url("redis://localhost:6379/0")


def test_telegram_log_is_not_the_operator_log(tmp_path):
    assert telegram_log.LOG_PATH.parent == tmp_path


def test_paid_and_telegram_credentials_are_not_inherited():
    assert settings.openai_api_key == ""
    assert settings.deepseek_api_key == ""
    assert settings.telegram_bot_token == ""
    assert settings.telegram_chat_id == ""


def test_async_external_http_is_also_blocked():
    async def request():
        async with httpx.AsyncClient() as client:
            await client.post("https://example.invalid/no-network", json={})
    with pytest.raises(AssertionError, match="External HTTP disabled"):
        asyncio.run(request())
