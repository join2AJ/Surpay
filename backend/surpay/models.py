from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    amount_cents: Mapped[int] = mapped_column(Integer)
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


class PreviousAddress(Base):
    __tablename__ = "previous_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[str] = mapped_column(String(2))
    zip: Mapped[str] = mapped_column(String(10), default="")

    user: Mapped[User] = relationship(back_populates="addresses")


class Claim(Base):
    """A user asking Surpay to pursue a specific surplus record for them."""

    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("user_id", "record_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("surplus_records.id"))
    # requested -> identity_verified -> agreement_signed -> filed -> approved -> paid | denied
    status: Mapped[str] = mapped_column(String(32), default="requested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="claims")
    record: Mapped[SurplusRecord] = relationship()
