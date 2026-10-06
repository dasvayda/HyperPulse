import pytest
from fastapi import HTTPException

from app.config import settings
from app.security import require_pipeline_run_token


def test_pipeline_run_token_rejects_missing_or_wrong_value(monkeypatch) -> None:
    monkeypatch.setattr(settings, "pipeline_run_token", "test-token")
    monkeypatch.setattr(settings, "environment", "production")

    for value in (None, "wrong-token"):
        with pytest.raises(HTTPException) as exc:
            require_pipeline_run_token(value)
        assert exc.value.status_code == 401


def test_pipeline_run_token_allows_matching_value(monkeypatch) -> None:
    monkeypatch.setattr(settings, "pipeline_run_token", "test-token")
    monkeypatch.setattr(settings, "environment", "production")

    require_pipeline_run_token("test-token")


def test_pipeline_run_fails_closed_in_production_without_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "pipeline_run_token", "")
    monkeypatch.setattr(settings, "environment", "production")

    with pytest.raises(HTTPException) as exc:
        require_pipeline_run_token(None)
    assert exc.value.status_code == 503


def test_pipeline_run_stays_available_for_local_development(monkeypatch) -> None:
    monkeypatch.setattr(settings, "pipeline_run_token", "")
    monkeypatch.setattr(settings, "environment", "development")

    require_pipeline_run_token(None)
