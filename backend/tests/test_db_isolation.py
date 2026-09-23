from app.config import settings


def test_pytest_does_not_use_live_hyperpulse_db():
    assert "hyperpulse.db" not in settings.database_url
    assert settings.database_url.startswith("sqlite:///")
