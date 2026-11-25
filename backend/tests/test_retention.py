"""Run against isolated SQLite, and PostgreSQL when explicitly supplied by CI."""
import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base
from app.models.orm import (
    AlertRow, BriefSessionRow, EvidenceRow, InferenceRow, MarketBriefRow,
    MarketSnapshotRow, PaperStrategyRow, PulseResultRow, PulseSignalRow,
)
from app.services import evidence, retention

NOW = datetime(2026, 11, 25, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=40)


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request, tmp_path, monkeypatch):
    root = None
    if request.param == "postgresql":
        url = os.getenv("RETENTION_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Isolated PostgreSQL URL not supplied")
        schema = "retention_test_" + uuid.uuid4().hex
        root = create_engine(url)
        with root.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'retention.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(settings, "retention_batch_size", 2)
    monkeypatch.setattr(settings, "retention_max_batches", 2)
    monkeypatch.setattr(settings, "retention_days", 7)
    monkeypatch.setattr(settings, "retention_pulse_days", 30)
    yield factory
    engine.dispose()
    if root:
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


def inference(key, at):
    return InferenceRow(id=key, trader_address="wallet", strategy="Mixed", trading_style="test",
                        risk_profile="test", created_at=at)


def pulse(key, at, ref=None):
    return PulseSignalRow(id=key, asset="BTC", direction="up", mark_at_emit=100,
                          evidence_id=ref, created_at=at)


def test_retention_preserves_latest_boundaries_and_paper(database):
    with database() as db:
        db.add_all([
            MarketSnapshotRow(asset="BTC", mark_price=1, timestamp=OLD),
            MarketSnapshotRow(asset="BTC", mark_price=2, timestamp=OLD + timedelta(seconds=1)),
            MarketSnapshotRow(asset="DELISTED", mark_price=3, timestamp=OLD),
            MarketSnapshotRow(asset="ETH", mark_price=4, timestamp=NOW - timedelta(days=7)),
            MarketSnapshotRow(asset="ETH", mark_price=5, timestamp=NOW),
            inference("old", OLD), inference("latest", OLD + timedelta(seconds=1)),
            PaperStrategyRow(id="paper", version="v1", config_hash="test", cash=999),
        ])
        db.commit()
    preview = retention.run_retention(now=NOW, apply=False, session_factory=database)
    assert preview["market_snapshots"] == 1 and preview["inference_results"] == 1
    with database() as db:
        assert db.query(MarketSnapshotRow).count() == 5
    retention.run_retention(now=NOW, session_factory=database)
    with database() as db:
        assert sorted(r.mark_price for r in db.query(MarketSnapshotRow)) == [2, 3, 4, 5]
        assert [r.id for r in db.query(InferenceRow)] == ["latest"]
        assert db.get(PaperStrategyRow, "paper").cash == 999
    assert not any(retention.run_retention(now=NOW, session_factory=database).values())


def test_all_evidence_references_protected_and_pulse_pair_pruned(database):
    with database() as db:
        db.add_all([EvidenceRow(id=k, body="{}", created_at=OLD)
                    for k in ("alert", "edition", "brief", "pending", "recent_pulse", "expired", "orphan")])
        db.add(EvidenceRow(id="fresh", body="{}", created_at=NOW))
        db.add(AlertRow(id="a", event_type="test", evidence_id="alert", title="t", message="m", created_at=OLD))
        db.add(BriefSessionRow(slot_id="s", label="Asia", evidence_id="edition", brief_json="{}", frozen_at=OLD, published_at=OLD))
        db.add(MarketBriefRow(id="latest", evidence_id="brief"))
        db.add_all([pulse("pending", OLD, "pending"), pulse("expired", OLD, "expired"),
                    pulse("recent", NOW - timedelta(days=15), "recent_pulse")])
        db.add_all([PulseResultRow(signal_id=k, outcome="up", resolved_at=NOW) for k in ("expired", "recent")])
        db.commit()
    retention.run_retention(now=NOW, session_factory=database)
    with database() as db:
        assert {r.id for r in db.query(EvidenceRow)} == {"alert", "edition", "brief", "pending", "recent_pulse", "fresh"}
        assert db.get(PulseResultRow, "expired") is None
        assert db.get(PulseSignalRow, "expired") is None
        assert db.get(PulseSignalRow, "pending") is not None


def test_batch_budget_is_enforced(database):
    with database() as db:
        db.add_all([EvidenceRow(id=str(i), body="{}", created_at=OLD) for i in range(10)])
        db.commit()
    assert retention.run_retention(now=NOW, session_factory=database)["signal_evidence"] == 4
    with database() as db:
        assert db.query(EvidenceRow).count() == 6


def test_compressed_and_legacy_evidence_round_trip(database, monkeypatch):
    monkeypatch.setattr(evidence, "SessionLocal", database)
    raw = '{"data":"' + "positions," * 10000 + '"}'
    key = hashlib.sha256(raw.encode()).hexdigest()
    with database() as db:
        evidence.save(db, (key, raw))
        db.commit()
        assert len(db.get(EvidenceRow, key).body) < len(raw) // 10
    assert evidence.retrieve(key)["data"] == "positions," * 10000
    with database() as db:
        db.get(EvidenceRow, key).body = raw
        db.commit()
    assert evidence.retrieve(key)["data"] == "positions," * 10000
    with database() as db:
        db.get(EvidenceRow, key).body = evidence.encode_body(raw.replace("positions", "different"))
        db.commit()
    with pytest.raises(ValueError, match="digest mismatch"):
        evidence.retrieve(key)


def test_coin_brief_repeat_reads_do_not_add_evidence(monkeypatch):
    from app.services import market_brief
    from app.db import SessionLocal
    from tests.conftest import seed_store
    seed_store()
    market_brief._coin_briefs.clear()
    first = asyncio.run(market_brief.generate_market_brief(asset="BTC"))
    with SessionLocal() as db:
        before = db.query(EvidenceRow).count()
    second = asyncio.run(market_brief.generate_market_brief(asset="BTC"))
    assert first.evidence_id == second.evidence_id
    assert first is not second
    with SessionLocal() as db:
        assert db.query(EvidenceRow).count() == before
    expired_at = market_brief._coin_briefs["BTC"][0] + 61
    monkeypatch.setattr(market_brief.time, "monotonic", lambda: expired_at)
    refreshed = asyncio.run(market_brief.generate_market_brief(asset="BTC"))
    assert refreshed.evidence_id != first.evidence_id
    forced = asyncio.run(market_brief.generate_market_brief(asset="BTC", force=True))
    assert forced.evidence_id != refreshed.evidence_id
    market_brief._coin_briefs.clear()


def test_transient_reset_keeps_durable_records(database, monkeypatch):
    from scripts import maintain_storage
    monkeypatch.setattr(maintain_storage, "SessionLocal", database)
    monkeypatch.setattr(maintain_storage, "engine", database.kw["bind"])
    with database() as db:
        db.add_all([EvidenceRow(id=k, body="{}") for k in ("keep", "edition", "brief", "drop")])
        db.add(AlertRow(id="a", event_type="test", evidence_id="keep", title="t", message="m"))
        db.add(BriefSessionRow(slot_id="s", label="Asia", evidence_id="edition", brief_json="{}", frozen_at=OLD, published_at=OLD))
        db.add(MarketBriefRow(id="latest", evidence_id="brief"))
        db.add(PaperStrategyRow(id="p", version="v1", config_hash="h", cash=999))
        db.add(MarketSnapshotRow(asset="BTC", mark_price=1))
        db.add(inference("i", NOW))
        db.add(pulse("p", NOW, "drop"))
        db.add(PulseResultRow(signal_id="p", outcome="up"))
        db.commit()
    maintain_storage.reset_transient()
    with database() as db:
        for model in (PulseSignalRow, PulseResultRow, InferenceRow, MarketSnapshotRow):
            assert db.query(model).count() == 0
        assert db.get(EvidenceRow, "keep") is not None
        assert db.get(EvidenceRow, "edition") is not None
        assert db.get(EvidenceRow, "brief") is not None
        assert db.get(EvidenceRow, "drop") is None
        assert db.get(PaperStrategyRow, "p").cash == 999
