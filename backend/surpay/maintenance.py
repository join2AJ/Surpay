"""Daily housekeeping: pass on unanswered case offers, and erase accounts past their retention period."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import attorneys, audit
from .models import Claim, Consent, Message, Notification, User

RETENTION_YEARS = 7          # signed claims: legal, tax and audit obligations
ABANDONED_DAYS = 180         # accounts that never verified an ID or started a claim
CLOSED = ("paid", "denied", "withdrawn")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _erase(session: Session, user: User, reason: str) -> None:
    uid = user.id
    for model, col in ((Notification, Notification.user_id), (Consent, Consent.user_id), (Message, Message.sender_id)):
        for row in session.scalars(select(model).where(col == uid)):
            session.delete(row)
    session.delete(user)
    audit.record(session, "account.erased", actor_type="system", entity_type="user", entity_id=uid,
                 details={"reason": reason})


def purge(session: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    expired_offers = attorneys.expire_offers(session)
    erased = 0
    for user in session.scalars(select(User)).all():
        if user.email.endswith("@surpay.test"):
            continue  # demo accounts reset themselves
        worked = session.scalar(select(Claim.id).where(Claim.attorney_id == user.id).limit(1)) is not None
        if user.deletion_requested_at is not None:
            done = all(c.status in CLOSED and _aware(c.updated_at) < now - timedelta(days=365 * RETENTION_YEARS)
                       for c in user.claims)
            if done and not worked:
                _erase(session, user, "deletion requested; retention period over")
                erased += 1
        elif (user.identity is None and not user.claims and user.attorney is None and not worked
              and _aware(user.created_at) < now - timedelta(days=ABANDONED_DAYS)):
            _erase(session, user, f"never verified; inactive {ABANDONED_DAYS} days")
            erased += 1
    session.commit()
    return {"expired_offers": expired_offers, "erased_accounts": erased}
