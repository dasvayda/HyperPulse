from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import orm  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        liq_columns = conn.execute(text("PRAGMA table_info(liquidations)")).fetchall()
        liq_names = {row[1] for row in liq_columns}
        if "tx_hash" not in liq_names:
            conn.execute(text("ALTER TABLE liquidations ADD COLUMN tx_hash VARCHAR(80)"))

        trader_columns = conn.execute(text("PRAGMA table_info(traders)")).fetchall()
        trader_names = {row[1] for row in trader_columns}
        if "account_value_usd" not in trader_names:
            conn.execute(text("ALTER TABLE traders ADD COLUMN account_value_usd FLOAT DEFAULT 0"))
        if "volume_usd" not in trader_names:
            conn.execute(text("ALTER TABLE traders ADD COLUMN volume_usd FLOAT DEFAULT 0"))

        snap_columns = conn.execute(text("PRAGMA table_info(market_snapshots)")).fetchall()
        snap_names = {row[1] for row in snap_columns}
        if "day_volume_usd" not in snap_names:
            conn.execute(text("ALTER TABLE market_snapshots ADD COLUMN day_volume_usd FLOAT DEFAULT 0"))
        if "prev_day_price" not in snap_names:
            conn.execute(text("ALTER TABLE market_snapshots ADD COLUMN prev_day_price FLOAT"))

        brief_columns = conn.execute(text("PRAGMA table_info(market_briefs)")).fetchall()
        brief_names = {row[1] for row in brief_columns}
        if brief_names:
            if "tldr_json" not in brief_names:
                conn.execute(text("ALTER TABLE market_briefs ADD COLUMN tldr_json TEXT DEFAULT '{}'"))
            if "asset" not in brief_names:
                conn.execute(text("ALTER TABLE market_briefs ADD COLUMN asset VARCHAR(32)"))
            if "stale" not in brief_names:
                conn.execute(text("ALTER TABLE market_briefs ADD COLUMN stale INTEGER DEFAULT 0"))
            if "tab_assets" not in brief_names:
                conn.execute(text("ALTER TABLE market_briefs ADD COLUMN tab_assets TEXT DEFAULT '[]'"))
