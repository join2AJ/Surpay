"""Fictional demo data and a one-tap demo account, for testing only.

Everything here is switched on by SURPAY_SEED_DEMO=true and must be off for real users.
People and places are made up ("Demo County") so they can't be mistaken for real records.
"""

import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crypto
from .auth import hash_password
from .ingest import upsert
from .models import IdentityVerification, Notification, PreviousAddress, SurplusRecord, User
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
    """Get the shared demo account in its starting state: profile filled in, ID approved, no claims.

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
    user.relatives = []
    user.addresses = [PreviousAddress(**DEMO_ADDRESS)]
    user.claims = []
    session.flush()
    if user.id is not None:
        for n in session.scalars(select(Notification).where(Notification.user_id == user.id)):
            session.delete(n)
    if user.identity is not None:  # delete first: one identity per person
        session.delete(user.identity)
    session.flush()
    # Pre-verified, so testers go straight to results. The "photos" are placeholders.
    placeholder = crypto.encrypt(b"\xff\xd8\xff\xe0demo-placeholder")
    user.identity = IdentityVerification(
        legal_name=DEMO_NAME, date_of_birth=date(1980, 4, 2), ssn_last4="0000", phone="555-010-0000",
        street=DEMO_ADDRESS["street"], city=DEMO_ADDRESS["city"], state="OH", zip=DEMO_ADDRESS["zip"],
        id_type="drivers_license", id_front=placeholder, selfie=placeholder,
        review_status="approved", review_note="Demo account",
    )
    session.commit()
    session.refresh(user)
    return user


DEMO_ATTORNEY_EMAIL = "attorney-demo@surpay.test"
DEMO_ATTORNEY_NAME = "Avery Counsel"
DEMO_CLIENT_EMAIL = "client-demo@surpay.test"
DEMO_CLIENT_NAME = "Casey Placeholder"
DEMO_CLIENT_ADDRESS = {"street": "19 Elm St", "city": "Springfield", "state": "OH", "zip": "45503",
                       "county": "Clark County"}
# A valid 1x1 white PNG standing in for the demo client's drawn signature.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c4944415408d763f8ffff3f0005fe02fe"
    "a7d6a4510000000049454e44ae426082")


def _demo_user(session: Session, email: str, name: str, role: str) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(24)), full_name=name,
                    other_names=[], phone="", role=role)
        session.add(user)
        session.flush()
    user.full_name, user.role, user.token_version = name, role, user.token_version or 0
    return user


def reset_demo_attorney(session: Session) -> User:
    """The shared demo attorney: approved for Demo County, OH, with one fresh verified case offered.

    The case belongs to a second fictional person (Casey Placeholder) who has verified their ID
    and signed, so testers see exactly what a real attorney receives.
    """
    from . import attorneys, claims, fees
    from .models import Agreement, AttorneyProfile, Claim

    if not session.scalar(select(SurplusRecord.id).where(SurplusRecord.source == "demo",
                                                         SurplusRecord.status == "listed").limit(1)):
        upsert(session, "demo", demo_records(), full_snapshot=True)
    placeholder = crypto.encrypt(b"\xff\xd8\xff\xe0demo-placeholder")

    lawyer = _demo_user(session, DEMO_ATTORNEY_EMAIL, DEMO_ATTORNEY_NAME, "attorney")
    if lawyer.attorney is None:
        lawyer.attorney = AttorneyProfile(
            full_name=DEMO_ATTORNEY_NAME, bar_state="OH", bar_number="0000000 (demo)", firm="Demo Counsel LLP",
            phone="555-010-0100", office_address="1 Court St, Springfield, OH 45501", counties=["Demo County"],
            bar_card=placeholder)
    lawyer.attorney.status, lawyer.attorney.review_note = "approved", "Demo attorney"
    lawyer.attorney.counties = ["Demo County"]
    for n in session.scalars(select(Notification).where(Notification.user_id == lawyer.id)):
        session.delete(n)

    client = _demo_user(session, DEMO_CLIENT_EMAIL, DEMO_CLIENT_NAME, "claimant")
    client.addresses = [PreviousAddress(**DEMO_CLIENT_ADDRESS)]
    client.claims = []
    if client.identity is not None:
        session.delete(client.identity)
    session.flush()
    client.identity = IdentityVerification(
        legal_name=DEMO_CLIENT_NAME, date_of_birth=date(1975, 9, 14), ssn_last4="0000", phone="555-010-0003",
        street=DEMO_CLIENT_ADDRESS["street"], city="Springfield", state="OH", zip="45503",
        id_type="drivers_license", id_front=placeholder, selfie=placeholder,
        review_status="approved", review_note="Demo account",
    )
    session.flush()

    record = session.scalar(select(SurplusRecord).where(SurplusRecord.source == "demo",
                                                        SurplusRecord.source_key == "D-1003"))
    claim = claims.new_claim(session, client, record.id)
    claim.record = record
    fees.for_claim(session, claim)
    text = claims.agreement_text(claim, client, claim.fee_pct)
    claim.agreement = Agreement(
        version=claims.AGREEMENT_VERSION, text=text, fee_pct=claim.fee_pct, signature_name=DEMO_CLIENT_NAME,
        legal_name_on_id=DEMO_CLIENT_NAME, document_sha256=crypto.sha256_hex(text),
        signature_image=crypto.encrypt(_PNG), ip_address="demo", device_info="Demo device")
    claims.advance(claim, "agreement_signed")
    claims.advance(claim, "identity_verified")
    session.flush()
    # Offer it to the demo attorney directly, whoever else serves Demo County.
    others = [a.user_id for a in session.scalars(select(AttorneyProfile).where(AttorneyProfile.status == "approved"))
              if a.user_id != lawyer.id]
    claim.declined_by = others
    attorneys.offer(session, claim)
    session.commit()
    session.refresh(lawyer)
    return lawyer
