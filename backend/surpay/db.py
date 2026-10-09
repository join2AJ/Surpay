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
    ("users", "token_version", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "deletion_requested_at", "TIMESTAMP WITH TIME ZONE"),
    ("previous_addresses", "relative_id", "INTEGER REFERENCES relatives(id) ON DELETE CASCADE"),
    ("claims", "relative_id", "INTEGER REFERENCES relatives(id)"),
    ("claims", "fee_pct", "FLOAT"),
    ("claims", "fee_basis", "JSON"),
    ("agreements", "signature_image", "{blob}"),
    ("agreements", "document_sha256", "VARCHAR(64) NOT NULL DEFAULT ''"),
    ("agreements", "device_id", "VARCHAR(128) NOT NULL DEFAULT ''"),
    ("agreements", "device_info", "VARCHAR(255) NOT NULL DEFAULT ''"),
    ("agreements", "legal_name_on_id", "VARCHAR(255) NOT NULL DEFAULT ''"),
    ("messages", "attorney_id", "INTEGER"),
]

# Identity details that became encrypted: their columns must hold ciphertext (Postgres only;
# SQLite doesn't enforce column types), and rows saved before are encrypted in place.
_ENCRYPTED_COLUMNS = ("date_of_birth", "ssn_last4", "phone", "street", "city", "zip")


def _encrypt_legacy_identity_rows(conn) -> None:
    from sqlalchemy import text

    from . import crypto

    cols = ", ".join(_ENCRYPTED_COLUMNS)
    for row in conn.execute(text(f"SELECT id, {cols} FROM identity_verifications")).mappings():
        plain = {c: row[c] for c in _ENCRYPTED_COLUMNS if row[c] is not None and not crypto.is_token(str(row[c]))}
        if plain:
            sets = ", ".join(f"{c} = :{c}" for c in plain)
            conn.execute(text(f"UPDATE identity_verifications SET {sets} WHERE id = :id"),
                         {**{c: crypto.encrypt(str(v).encode()).decode() for c, v in plain.items()}, "id": row["id"]})


def init_db(bind=None) -> None:
    from sqlalchemy import inspect, text

    from . import models  # noqa: F401  (registers tables)

    bind = bind or engine
    Base.metadata.create_all(bind)
    inspector = inspect(bind)
    postgres = bind.dialect.name == "postgresql"
    with bind.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            if column not in {c["name"] for c in inspector.get_columns(table)}:
                ddl = ddl.format(blob="BYTEA" if postgres else "BLOB")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        if postgres:
            types = {c["name"]: str(c["type"]).upper() for c in inspector.get_columns("identity_verifications")}
            for column in _ENCRYPTED_COLUMNS:
                if types.get(column) != "TEXT":
                    conn.execute(text(f"ALTER TABLE identity_verifications ALTER COLUMN {column} "
                                      f"TYPE TEXT USING {column}::text"))
        _encrypt_legacy_identity_rows(conn)

    from .fees import seed_defaults
    with SessionLocal(bind=bind) as session:
        seed_defaults(session)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
