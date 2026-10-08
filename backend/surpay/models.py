from datetime import date, datetime, timezone

from sqlalchemy import JSON, BigInteger, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SurplusRecord(Base):
    """One pot of surplus money held by a county or court, as published by a source."""

    __tablename__ = "surplus_records"
    __table_args__ = (UniqueConstraint("source", "source_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    # Stable identity within the source (case number, parcel + sale date, ...).
    source_key: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(2), index=True)
    county: Mapped[str] = mapped_column(String(64))
    sale_type: Mapped[str] = mapped_column(String(32))  # "tax_sale" | "mortgage_foreclosure"
    reference: Mapped[str] = mapped_column(String(255))  # parcel(s) or case number shown to users
    owner_name: Mapped[str] = mapped_column(String(255))
    owner_name_norm: Mapped[str] = mapped_column(String(255), index=True)
    owner_address: Mapped[str] = mapped_column(String(255), default="")
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, default="")
    # "listed" while the source still publishes it; "delisted" once it drops off
    # (usually paid out or forfeited).
    status: Mapped[str] = mapped_column(String(16), default="listed", index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ok: Mapped[bool] = mapped_column(default=False)
    added: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    delisted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    # Other names the person may appear under (maiden name, nicknames).
    other_names: Mapped[list] = mapped_column(JSON, default=list)
    phone: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    addresses: Mapped[list["PreviousAddress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="PreviousAddress.id"
    )
    claims: Mapped[list["Claim"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    identity: Mapped["IdentityVerification | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False)


class PreviousAddress(Base):
    __tablename__ = "previous_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[str] = mapped_column(String(2))
    zip: Mapped[str] = mapped_column(String(10), default="")
    county: Mapped[str] = mapped_column(String(64), default="")

    user: Mapped[User] = relationship(back_populates="addresses")


class Claim(Base):
    """A user asking Surpay to pursue a specific surplus record for them."""

    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("user_id", "record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("surplus_records.id"))
    # See surpay/claims.py for the steps: requested -> identity_submitted -> agreement_signed ->
    # identity_verified -> filed -> approved -> paid, or denied / withdrawn.
    status: Mapped[str] = mapped_column(String(32), default="requested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="claims")
    record: Mapped[SurplusRecord] = relationship()
    events: Mapped[list["ClaimEvent"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="ClaimEvent.id")
    agreement: Mapped["Agreement | None"] = relationship(
        back_populates="claim", cascade="all, delete-orphan", uselist=False)


class ClaimEvent(Base):
    """Each status a claim reached, and when: the claim's history and timeline."""

    __tablename__ = "claim_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    claim: Mapped[Claim] = relationship(back_populates="events")


class IdentityVerification(Base):
    """What a claimant submitted to prove who they are. One per user, reused for every claim.

    Document images are encrypted (surpay/crypto.py) before they are stored.
    """

    __tablename__ = "identity_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[date] = mapped_column(Date)
    ssn_last4: Mapped[str] = mapped_column(String(4))
    phone: Mapped[str] = mapped_column(String(32))
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(2))
    zip: Mapped[str] = mapped_column(String(10))
    id_type: Mapped[str] = mapped_column(String(32))  # drivers_license | state_id | passport
    id_front: Mapped[bytes] = mapped_column(LargeBinary)
    id_back: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    selfie: Mapped[bytes] = mapped_column(LargeBinary)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # pending -> approved | rejected (rejected: the person can submit again)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="identity")


class Agreement(Base):
    """The contingency agreement a claimant e-signed for one claim, kept exactly as shown."""

    __tablename__ = "agreements"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), unique=True)
    version: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    fee_pct: Mapped[float] = mapped_column()
    signature_name: Mapped[str] = mapped_column(String(255))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")

    claim: Mapped[Claim] = relationship(back_populates="agreement")


class CountySource(Base):
    """Where (and whether) a county publishes its surplus list. Seeded from data/county_sources.csv."""

    __tablename__ = "county_sources"

    fips: Mapped[str] = mapped_column(String(5), primary_key=True)
    state: Mapped[str] = mapped_column(String(2), index=True)
    county: Mapped[str] = mapped_column(String(64))
    # unresearched | scraper_live | list_online | request_only | notices_only |
    # special_process | closed | do_not_use
    status: Mapped[str] = mapped_column(String(32), index=True, default="unresearched")
    difficulty: Mapped[str] = mapped_column(String(16), default="unknown")  # easy | medium | hard | blocked
    publisher: Mapped[str] = mapped_column(String(128), default="")
    format: Mapped[str] = mapped_column(String(64), default="")
    list_url: Mapped[str] = mapped_column(Text, default="")
    update_frequency: Mapped[str] = mapped_column(String(64), default="")
    scraper: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    last_verified: Mapped[str] = mapped_column(String(10), default="")
    # Filled in by `check-sources`.
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    last_changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_error: Mapped[str] = mapped_column(Text, default="")
