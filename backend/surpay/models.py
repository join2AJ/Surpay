from datetime import date, datetime, timezone

from sqlalchemy import JSON, BigInteger, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .crypto import EncryptedDate, EncryptedText
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
    # claimant (default) | attorney
    role: Mapped[str] = mapped_column(String(16), default="claimant")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Bumped on sign-out-everywhere and password change: older tokens stop working.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    # Set when the person asks for their account and data to be erased.
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    addresses: Mapped[list["PreviousAddress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="PreviousAddress.id"
    )
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="Claim.user_id")
    identity: Mapped["IdentityVerification | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False)
    attorney: Mapped["AttorneyProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False)
    relatives: Mapped[list["Relative"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Relative.id")

    @property
    def own_addresses(self) -> list["PreviousAddress"]:
        return [a for a in self.addresses if a.relative_id is None]


class PreviousAddress(Base):
    __tablename__ = "previous_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[str] = mapped_column(String(2))
    zip: Mapped[str] = mapped_column(String(10), default="")
    county: Mapped[str] = mapped_column(String(64), default="")
    # Set when this was a family member's home (searching for them as their heir), not the user's.
    relative_id: Mapped[int | None] = mapped_column(ForeignKey("relatives.id", ondelete="CASCADE"), nullable=True)

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

    # Case allotment: the attorney currently offered or handling this claim.
    attorney_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # "" (not assigned) | offered | accepted
    assignment_status: Mapped[str] = mapped_column(String(16), default="")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Attorneys who declined; never offered this claim again.
    declined_by: Mapped[list] = mapped_column(JSON, default=list)
    attorney_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    # "" | due (case finished, attorney to be paid) | paid
    payout_status: Mapped[str] = mapped_column(String(16), default="")
    # Claiming as a family member's heir (or under a power of attorney) rather than for themself.
    relative_id: Mapped[int | None] = mapped_column(ForeignKey("relatives.id"), nullable=True)
    # Contingency fee for this case, fixed when the claim starts (surpay/fees.py) and how it was
    # worked out. Staff may override it before the agreement is signed.
    fee_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fee_basis: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped[User] = relationship(back_populates="claims", foreign_keys=[user_id])
    attorney: Mapped["User | None"] = relationship(foreign_keys=[attorney_id])
    record: Mapped[SurplusRecord] = relationship()
    relative: Mapped["Relative | None"] = relationship()
    events: Mapped[list["ClaimEvent"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="ClaimEvent.id")
    agreement: Mapped["Agreement | None"] = relationship(
        back_populates="claim", cascade="all, delete-orphan", uselist=False)
    messages: Mapped[list["Message"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="Message.id")


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

    Document images and personal details are encrypted (surpay/crypto.py) before they are
    stored. The legal name stays searchable because matching needs it.
    """

    __tablename__ = "identity_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[date] = mapped_column(EncryptedDate)
    ssn_last4: Mapped[str] = mapped_column(EncryptedText)
    phone: Mapped[str] = mapped_column(EncryptedText)
    street: Mapped[str] = mapped_column(EncryptedText)
    city: Mapped[str] = mapped_column(EncryptedText)
    state: Mapped[str] = mapped_column(String(2))
    zip: Mapped[str] = mapped_column(EncryptedText)
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
    # Evidence of who signed: their drawn signature (encrypted PNG), a fingerprint of the exact
    # text signed, the device it was signed on and the name on their verified ID.
    signature_image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    document_sha256: Mapped[str] = mapped_column(String(64), default="")
    device_id: Mapped[str] = mapped_column(String(128), default="")
    device_info: Mapped[str] = mapped_column(String(255), default="")
    legal_name_on_id: Mapped[str] = mapped_column(String(255), default="")

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


class AttorneyProfile(Base):
    """A lawyer who files claims for Surpay clients in the counties they serve, paid per case."""

    __tablename__ = "attorney_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    bar_state: Mapped[str] = mapped_column(String(2), index=True)
    bar_number: Mapped[str] = mapped_column(String(64))
    firm: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(32))
    office_address: Mapped[str] = mapped_column(String(255))
    # County names exactly as in the county registry, e.g. ["Dallas County", "Collin County"].
    counties: Mapped[list] = mapped_column(JSON, default=list)
    bar_card: Mapped[bytes] = mapped_column(LargeBinary)  # encrypted photo of bar card / license
    terms_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # pending -> approved | rejected (rejected may re-apply)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="attorney")

    def serves(self, county: str, state: str) -> bool:
        """Licensed in the state and serving the county ("Dallas" matches "Dallas County")."""
        if state.upper() != self.bar_state:
            return False
        want = county.lower().removesuffix(" county").strip()
        return any(c.lower().removesuffix(" county").strip() == want for c in self.counties)


class Relative(Base):
    """A family member whose surplus the user claims as their heir (or holds legal authority for).

    Searches for a relative's name unlock only after staff check the relationship documents,
    so nobody can use the app to look up an unrelated person.
    """

    __tablename__ = "relatives"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    other_names: Mapped[list] = mapped_column(JSON, default=list)
    # spouse | parent | child | sibling | grandparent | grandchild | other
    relation: Mapped[str] = mapped_column("relationship", String(32))
    # heir (they have died) | power_of_attorney | guardian
    basis: Mapped[str] = mapped_column(String(32), default="heir")
    date_of_death: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    # Encrypted document photos.
    death_certificate: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    relationship_proof: Mapped[bytes] = mapped_column(LargeBinary)
    authority_document: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # pending -> approved | rejected
    review_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="relatives")
    addresses: Mapped[list[PreviousAddress]] = relationship(viewonly=True)


class Message(Base):
    """In-app chat between a claimant and their attorney about one claim. Encrypted at rest."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sender_role: Mapped[str] = mapped_column(String(16))  # attorney | claimant
    body: Mapped[str] = mapped_column(EncryptedText)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    claim: Mapped[Claim] = relationship(back_populates="messages")


class Notification(Base):
    """Something to tell a user: claim progress, a new message, a new case. Shown in the app and
    as a phone notification."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # claim_update | message | case_offer | money_released | ...
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Consent(Base):
    """A record of each notice a person accepted (terms, privacy, ID processing...), and when."""

    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    device_id: Mapped[str] = mapped_column(String(128), default="")
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Tamper-evident record of every significant action: who, what, when, from where.

    Each entry stores the hash of the previous one, so editing or deleting any past entry
    breaks the chain (`GET /admin/audit/verify`). Never updated or deleted by the app.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_type: Mapped[str] = mapped_column(String(16))  # user | attorney | admin | system
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    device_id: Mapped[str] = mapped_column(String(128), default="")
    device_info: Mapped[str] = mapped_column(String(255), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="")


class FeeRule(Base):
    """Staff-set fee inputs for a whole state (county = "") or one county.

    base_pct: the usual rate there. legal_max_pct: the most the law allows (None = no known cap).
    """

    __tablename__ = "fee_rules"
    __table_args__ = (UniqueConstraint("state", "county"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(2))
    county: Mapped[str] = mapped_column(String(64), default="")
    base_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    legal_max_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    legal_source: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FeeBand(Base):
    """Rate by size of the recovery: smaller amounts carry a higher percentage."""

    __tablename__ = "fee_bands"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Applies to amounts up to and including this; None = everything above the other bands.
    up_to_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pct: Mapped[float] = mapped_column(Float)
