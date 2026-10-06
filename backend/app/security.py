"""Small guards for endpoints that must never be publicly callable in production."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import settings


def require_pipeline_run_token(
    x_pipeline_token: Annotated[str | None, Header()] = None,
) -> None:
    """Protect the manual pipeline trigger without adding end-user auth yet.

    Local development may omit the token. Production-like environments fail
    closed when it is missing so a public deployment cannot expose a costly
    collector/LLM/Telegram run endpoint by configuration accident.
    """

    expected = settings.pipeline_run_token
    if not expected:
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Pipeline run token is not configured",
            )
        return

    if not x_pipeline_token or not secrets.compare_digest(x_pipeline_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid pipeline run token",
        )
