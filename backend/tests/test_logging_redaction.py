import io
import logging

import pytest

from app.config import settings
from app.logging_config import SecretRedactingFormatter, configure_logging, redact_secrets


@pytest.mark.parametrize("message,secret", [
    ("https://api.telegram.org/bot123456:UNCONFIGURED_TEST_TOKEN/sendMessage", "123456:UNCONFIGURED_TEST_TOKEN"),
    ("postgresql://admin:unknown-password@db:5432/hyperpulse", "unknown-password"),
    ("redis://:unknown-password@redis/0", "unknown-password"),
    ("Authorization: Bearer unconfigured-secret", "unconfigured-secret"),
    ('{"api_key": "unknown-key", "password": "db-pass"}', "unknown-key"),
    ("https://provider.test?access_token=unknown-token&ok=true", "unknown-token"),
    ("failed with sk-proj-12345678901234567890", "sk-proj-12345678901234567890"),
])
def test_patterns_redact_unconfigured_credentials(message, secret):
    output = redact_secrets(message)
    assert secret not in output
    assert "[REDACTED]" in output


def test_configured_secret_and_encoded_database_password_are_removed(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-private-key")
    monkeypatch.setattr(settings, "pipeline_run_token", "private-ops-token")
    monkeypatch.setattr(settings, "database_url", "postgresql://user:p%40ss%2Fword@db/app")
    output = redact_secrets("test-private-key private-ops-token p@ss/word p%40ss%2Fword")
    assert output == "[REDACTED] [REDACTED] [REDACTED] [REDACTED]"


def test_exception_traceback_and_interpolated_arguments_are_redacted(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:TEST_ONLY_SECRET")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SecretRedactingFormatter("%(levelname)s %(message)s"))
    logger = logging.Logger("redaction-test", level=logging.INFO)
    logger.addHandler(handler)
    try:
        raise RuntimeError("POST https://api.telegram.org/bot123456:TEST_ONLY_SECRET/sendMessage")
    except RuntimeError:
        logger.exception("Send failed for %s", settings.telegram_bot_token)
    output = stream.getvalue()
    assert "Traceback" in output and "RuntimeError" in output
    assert "TEST_ONLY_SECRET" not in output
    assert "[REDACTED]" in output


def test_non_sensitive_context_is_preserved():
    assert redact_secrets("collector failed HTTP 429 after 123ms") == "collector failed HTTP 429 after 123ms"


def test_uvicorn_handlers_are_protected(monkeypatch):
    handler = logging.StreamHandler(io.StringIO())
    logger = logging.getLogger("uvicorn.access")
    monkeypatch.setattr(logger, "handlers", [handler])
    configure_logging()
    assert isinstance(handler.formatter, SecretRedactingFormatter)
