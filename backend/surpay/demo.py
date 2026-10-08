"""Fictional demo data and a one-tap demo account, for testing only.

Everything here is switched on by SURPAY_SEED_DEMO=true and must be off for real users.
People and places are made up ("Demo County") so they can't be mistaken for real records.
"""

import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .ingest import upsert
from .models import PreviousAddress, SurplusRecord, User
from .scrapers.base import RecordIn

DEMO_EMAIL = "demo@surpay.test"
DEMO_NAME = "Jordan Testwell"
DEMO_ADDRESS = {"street": "412 Maple Ridge Rd", "city": "Springfield", "state": "OH", "zip": "45501",
                "county": "Clark County"}


def demo_records() -> list[RecordIn]:
    rows = [
        ("D-1001", "Jordan Testwell", "412 Maple Ridge Rd, Springfield, OH 45501", 2_845_000, date(2024, 6, 17)),
        ("D-1002", "TESTWELL, JORDAN A", "88 Harbor View Dr, Springfield, OH 45502", 612_550, date(2023, 11, 6)),
        ("D-1003", "Casey Placeholder", "19 Elm St, Springfield, OH 45503", 1_210_000, date(2024, 2, 12)),
        ("D-1004", "Morgan & Riley Example", "7 Birch Ct, Springfield, OH 45504", 4_390_075, date(2024, 9, 9)),
        ("D-1005", "Avery Sampleton", "230 Lake Shore Blvd, Springfield, OH 45505", 98_013, date(2025, 1, 21)),
    ]
    return [
        RecordIn(source_key=key, state="OH", county="Demo", sale_type="tax_sale", reference=f"Case {key}",
                 owner_name=name, owner_address=addr, amount_cents=cents, sale_date=sold,
                 source_url="", raw={"demo": True})
        for key, name, addr, cents, sold in rows
    ]


def reset_demo_user(session: Session) -> User:
    """Get the shared demo account in its starting state: profile filled in, no claims, no ID.

    Testers share this account, so each demo sign-in starts fresh.
    """
    if not session.scalar(select(SurplusRecord.id).where(SurplusRecord.source == "demo",
                                                         SurplusRecord.status == "listed").limit(1)):
        upsert(session, "demo", demo_records(), full_snapshot=True)

    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        # Random password: the account is only reachable through the demo button.
        user = User(email=DEMO_EMAIL, password_hash=hash_password(secrets.token_urlsafe(24)),
                    full_name=DEMO_NAME, other_names=[], phone="")
        session.add(user)
    user.full_name = DEMO_NAME
    user.other_names = []
    user.phone = ""
    user.addresses = [PreviousAddress(**DEMO_ADDRESS)]
    user.claims = []
    user.identity = None
    session.commit()
    session.refresh(user)
    return user
