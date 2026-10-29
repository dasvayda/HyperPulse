"""Redact secrets at the output boundary, including formatted tracebacks.

Never log request/response bodies or settings dumps. This is a second line of
defence for provider exceptions that embed credential-bearing URLs.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote, quote_plus, unquote, urlsplit

from app.config import settings

REDACTED = "[REDACTED]"
_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:[a-z_]*api[_-]?key|[a-z_]*token|password|passwd|authorization|x-pipeline-token)"
    r"[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&}]+)"
)
_USERINFO = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/\s@]+@")
_TELEGRAM = re.compile(r"/bot\d+:[A-Za-z0-9_-]+")
_AUTH = re.compile(r"(?i)(\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]+")
_API_KEY = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}")


def redact_secrets(text: str) -> str:
    secrets = [settings.telegram_bot_token, settings.openai_api_key,
               settings.deepseek_api_key, settings.cmc_api_key, settings.pipeline_run_token]
    for url in (settings.database_url, settings.redis_url):
        try:
            password = urlsplit(url).password
            if password:
                secrets.extend((password, unquote(password)))
        except ValueError:
            pass
    # Longest first avoids leaking suffixes when one credential prefixes another.
    variants = {encoded for secret in secrets if secret
                for encoded in (secret, quote(secret, safe=""), quote_plus(secret))}
    for secret in sorted(variants, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = _USERINFO.sub(r"\1" + REDACTED + "@", text)
    text = _TELEGRAM.sub("/bot" + REDACTED, text)
    text = _AUTH.sub(r"\1" + REDACTED, text)
    text = _API_KEY.sub(REDACTED, text)
    return _ASSIGNMENT.sub(r"\1" + REDACTED, text)


class SecretRedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    formatter = SecretRedactingFormatter(
        "%(asctime)s %(levelname)s:%(name)s:%(message)s", datefmt="%H:%M:%S",
    )
    # Uvicorn can install non-propagating handlers before importing app.main.
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "httpcore"):
        for handler in logging.getLogger(name).handlers:
            handler.setFormatter(formatter)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
