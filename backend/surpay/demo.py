"""Fictional demo data and a one-tap demo account, for testing only.

Everything here is switched on by SURPAY_SEED_DEMO=true and must be off for real users.
People and places are made up ("Demo County") so they can't be mistaken for real records.
"""

import secrets
from datetime import date, timedelta

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
    # Sale dates count back from today so the demo always shows every deadline colour (Ohio allows
    # about 3 years): D-1001 ~10 months left, D-1002 ~25 days (urgent), D-1003 ~4 months.
    today = date.today()
    ago = lambda days: today - timedelta(days=days)  # noqa: E731
    rows = [
        ("D-1001", "Jordan Testwell", "412 Maple Ridge Rd, Springfield, OH 45501", 2_845_000, ago(790)),
        ("D-1002", "TESTWELL, JORDAN A", "88 Harbor View Dr, Springfield, OH 45502", 612_550, ago(1070)),
        ("D-1003", "Casey Placeholder", "19 Elm St, Springfield, OH 45503", 1_210_000, ago(970)),
        ("D-1004", "Morgan & Riley Example", "7 Birch Ct, Springfield, OH 45504", 4_390_075, ago(700)),
        ("D-1005", "Avery Sampleton", "230 Lake Shore Blvd, Springfield, OH 45505", 98_013, ago(600)),
    ]
    return [
        RecordIn(source_key=key, state="OH", county="Demo", sale_type="tax_sale", reference=f"Case {key}",
                 owner_name=name, owner_address=addr, amount_cents=cents, sale_date=sold,
                 source_url="", raw={"demo": True})
        for key, name, addr, cents, sold in rows
    ]


def _ensure_records(session: Session) -> None:
    if not session.scalar(select(SurplusRecord.id).where(SurplusRecord.source == "demo",
                                                         SurplusRecord.status == "listed").limit(1)):
        upsert(session, "demo", demo_records(), full_snapshot=True)


def _clear_activity(session: Session, user: User) -> None:
    """Remove a demo account's claims, family members, notifications and messages."""
    from .models import Message, OneTimeCode, SignedDocument
    user.claims = []
    user.relatives = []
    session.flush()
    for model, col in ((Notification, Notification.user_id), (Message, Message.sender_id),
                       (OneTimeCode, OneTimeCode.user_id), (SignedDocument, SignedDocument.user_id)):
        for row in session.scalars(select(model).where(col == user.id)):
            session.delete(row)


def _jordan(session: Session, fresh: bool) -> User:
    """The demo claimant: profile filled in and ID approved, so testers go straight to results."""
    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is not None and not fresh and user.identity is not None:
        return user
    if user is None:
        # Random password: the account is only reachable through the demo button.
        user = User(email=DEMO_EMAIL, password_hash=hash_password(secrets.token_urlsafe(24)),
                    full_name=DEMO_NAME, other_names=[], phone="")
        session.add(user)
        session.flush()
    user.full_name, user.other_names, user.phone = DEMO_NAME, [], ""
    _clear_activity(session, user)
    user.addresses = [PreviousAddress(**DEMO_ADDRESS)]
    if user.identity is not None:  # delete first: one identity per person
        session.delete(user.identity)
        session.flush()
    placeholder = crypto.encrypt(b"\xff\xd8\xff\xe0demo-placeholder")
    user.identity = IdentityVerification(
        legal_name=DEMO_NAME, date_of_birth=date(1980, 4, 2), ssn_last4="0000", phone="555-010-0000",
        street=DEMO_ADDRESS["street"], city=DEMO_ADDRESS["city"], state="OH", zip=DEMO_ADDRESS["zip"],
        id_type="drivers_license", id_front=placeholder, selfie=placeholder,
        review_status="approved", review_note="Demo account",
    )
    session.flush()
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


def _avery(session: Session, fresh: bool) -> User:
    """The demo attorney: approved for Demo County, OH."""
    from .models import AttorneyProfile
    lawyer = _demo_user(session, DEMO_ATTORNEY_EMAIL, DEMO_ATTORNEY_NAME, "attorney")
    if lawyer.attorney is None:
        lawyer.attorney = AttorneyProfile(
            full_name=DEMO_ATTORNEY_NAME, bar_state="OH", bar_number="0000000 (demo)", firm="Demo Counsel LLP",
            phone="555-010-0100", office_address="1 Court St, Springfield, OH 45501", counties=["Demo County"],
            bar_card=crypto.encrypt(b"\xff\xd8\xff\xe0demo-placeholder"))
    lawyer.attorney.status, lawyer.attorney.review_note = "approved", "Demo attorney"
    lawyer.attorney.counties = ["Demo County"]
    lawyer.attorney.available = True
    if fresh:
        for n in session.scalars(select(Notification).where(Notification.user_id == lawyer.id)):
            session.delete(n)
    session.flush()
    return lawyer


def _casey_case(session: Session, fresh: bool) -> None:
    """A second fictional client (Casey) whose verified, signed case waits for the demo attorney, so
    the attorney side has something to accept even before anyone has tried the claimant demo."""
    from . import attorneys, claims, fees
    from .models import Agreement

    client = _demo_user(session, DEMO_CLIENT_EMAIL, DEMO_CLIENT_NAME, "claimant")
    if client.claims and not fresh:
        return
    _clear_activity(session, client)
    client.addresses = [PreviousAddress(**DEMO_CLIENT_ADDRESS)]
    if client.identity is not None:
        session.delete(client.identity)
        session.flush()
    placeholder = crypto.encrypt(b"\xff\xd8\xff\xe0demo-placeholder")
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
    attorneys.offer(session, claim)


# A shared demo left alone this long starts over at the next demo sign-in.
DEMO_IDLE_RESET_HOURS = 12


def _idle(session: Session) -> bool:
    from datetime import datetime, timedelta, timezone

    from .models import AuditLog
    last = session.scalar(select(AuditLog.at).where(AuditLog.action.in_(("auth.demo_login", "demo.reset")))
                          .order_by(AuditLog.id.desc()).limit(1))
    if last is None:
        return True
    last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    return last < datetime.now(timezone.utc) - timedelta(hours=DEMO_IDLE_RESET_HOURS)


def demo_world(session: Session, reset: bool = False) -> dict[str, User]:
    """The connected demo: Jordan (claimant), Avery (attorney for Demo County) and Casey (Avery's
    other client). Signing in as any of them keeps everyone's progress, so a claim Jordan signs is
    offered to Avery, Avery's messages reach Jordan, and so on. `reset`, or 12 idle hours, starts over.
    """
    fresh = reset or _idle(session)
    _ensure_records(session)
    lawyer = _avery(session, fresh)
    jordan = _jordan(session, fresh)
    _casey_case(session, fresh)
    session.commit()
    session.refresh(jordan)
    session.refresh(lawyer)
    return {"claimant": jordan, "attorney": lawyer}


def reset_demo_user(session: Session) -> User:
    """Start the whole demo over and return the claimant."""
    return demo_world(session, reset=True)["claimant"]


def reset_demo_attorney(session: Session) -> User:
    """Start the whole demo over and return the attorney."""
    return demo_world(session, reset=True)["attorney"]


def is_demo_user(user) -> bool:
    """The fictional demo accounts (Jordan, Casey, Avery). Real testers' data is never shown to the demo admin."""
    return user is not None and user.email.endswith("@surpay.test")


def is_demo_claim(claim) -> bool:
    return claim.record is not None and claim.record.source == "demo"


def is_demo_attorney(profile) -> bool:
    """An attorney who only serves Demo County can only ever get demo cases."""
    counties = {c.lower().removesuffix(" county").strip() for c in (profile.counties or [])}
    return bool(counties) and counties <= {"demo"}
