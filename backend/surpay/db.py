from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


def make_engine(url: str = config.DATABASE_URL):
    # Neon suspends idle databases and drops their connections: check before reusing one.
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Columns added after a table first shipped. create_all() makes new tables but never alters
# existing ones, so these are added in place (works on SQLite and Postgres).
_ADDED_COLUMNS = [
    ("previous_addresses", "county", "VARCHAR(64) NOT NULL DEFAULT ''"),
    ("users", "role", "VARCHAR(16) NOT NULL DEFAULT 'claimant'"),
    ("claims", "attorney_id", "INTEGER REFERENCES users(id)"),
    ("claims", "assignment_status", "VARCHAR(16) NOT NULL DEFAULT ''"),
    ("claims", "assigned_at", "TIMESTAMP WITH TIME ZONE"),
    ("claims", "accepted_at", "TIMESTAMP WITH TIME ZONE"),
    ("claims", "declined_by", "JSON"),
    ("claims", "attorney_fee_cents", "INTEGER NOT NULL DEFAULT 0"),
    ("claims", "payout_status", "VARCHAR(16) NOT NULL DEFAULT ''"),
]


def init_db(bind=None) -> None:
    from sqlalchemy import inspect, text

    from . import models  # noqa: F401  (registers tables)

    bind = bind or engine
    Base.metadata.create_all(bind)
    inspector = inspect(bind)
    with bind.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            if column not in {c["name"] for c in inspector.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
