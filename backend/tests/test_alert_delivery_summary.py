from datetime import datetime, timedelta, timezone

from app.models.schemas import AlertHistoryItem
from app.routers.v2 import alert_delivery_summary
from app.services.store import store


def _alert(status: str, *, age_hours: int = 0) -> AlertHistoryItem:
    created = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    return AlertHistoryItem(
        id=f"{status}-{age_hours}",
        channel="telegram",
        event_type="test",
        title="test",
        message="test",
        status=status,
        created_at=created,
        sent_at=created if status == "sent" else None,
    )


def test_alert_delivery_summary_counts_recent_send_outcomes(monkeypatch) -> None:
    monkeypatch.setattr(
        store,
        "alerts",
        [_alert("sent"), _alert("failed"), _alert("queued"), _alert("sent", age_hours=25)],
    )
    result = alert_delivery_summary()

    assert result.sent == 1
    assert result.failed == 1
    assert result.queued == 1
    assert result.attempted == 2
    assert result.delivery_rate_pct == 50.0
