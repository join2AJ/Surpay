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
    reminders = deadline_reminders(session, now.date())
    session.commit()
    return {"expired_offers": expired_offers, "erased_accounts": erased, "deadline_reminders": reminders}


REMINDER_DAYS = (90, 60, 30, 14, 7, 3, 1)
UNCLAIMED_REMINDER_DAYS = (90, 30, 7)


def _due_milestone(days_left: int | None, milestones: tuple[int, ...]) -> int | None:
    """The smallest milestone we've reached (days_left <= m), or None."""
    if days_left is None or days_left < 0:
        return None
    hit = [m for m in milestones if days_left <= m]
    return min(hit) if hit else None


def _sent(session: Session, user_id: int, kind: str, claim_id: int | None, title: str | None = None) -> bool:
    stmt = select(Notification.id).where(Notification.user_id == user_id, Notification.kind == kind,
                                         Notification.claim_id == claim_id if claim_id else Notification.claim_id.is_(None))
    if title:
        stmt = stmt.where(Notification.title == title)
    return session.scalar(stmt.limit(1)) is not None


def deadline_reminders(session: Session, today=None) -> int:
    """Warn claimants and their attorneys as the legal deadline to claim gets close.

    Once per milestone (90, 60, 30, 14, 7, 3 and 1 days left) for claims not yet filed, and at 90, 30
    and 7 days for money a verified user matches but hasn't started a claim on.
    """
    from .legal import record_deadline
    from .matching import find_all_matches

    sent = 0
    for c in session.scalars(select(Claim).where(Claim.status.not_in(CLOSED))).all():
        r = c.record
        clock = record_deadline(r, c.status, as_of=today)
        m = _due_milestone(clock["days_left"], REMINDER_DAYS)
        if m is None or clock["urgency"] == "met":
            continue
        kind = f"deadline_{m}"
        where = f"{r.county} County, {r.state}"
        if not _sent(session, c.user_id, kind, c.id):
            todo = {"requested": "Verify your ID and sign the agreement today",
                    "identity_submitted": "We're checking your ID; watch for the agreement to sign",
                    "agreement_signed": "We're finishing the ID check so an attorney can file",
                    }.get(c.status, "Your attorney is preparing the filing; reply quickly to any request")
            session.add(Notification(user_id=c.user_id, kind=kind, claim_id=c.id,
                                     title=f"{clock['label']} to claim ${r.amount_cents / 100:,.2f}",
                                     body=f"The deadline for your claim in {where} is {clock['deadline']:%B %-d, %Y}. {todo}."))
            sent += 1
        if c.attorney_id and c.assignment_status == "accepted" and not _sent(session, c.attorney_id, kind, c.id):
            session.add(Notification(user_id=c.attorney_id, kind=kind, claim_id=c.id,
                                     title=f"SP-{c.id:06d}: {clock['label']} to file",
                                     body=f"File in {where} by {clock['deadline']:%B %-d, %Y} "
                                          f"(aim for {clock['file_by']:%B %-d, %Y})."))
            sent += 1

    for user in session.scalars(select(User)).all():
        if user.identity is None or user.identity.review_status != "approved" or user.suspended_at is not None:
            continue
        claimed = {c.record_id for c in user.claims}
        for match in find_all_matches(session, user):
            r = match.record
            if r.id in claimed:
                continue
            clock = record_deadline(r, as_of=today)
            m = _due_milestone(clock["days_left"], UNCLAIMED_REMINDER_DAYS)
            if m is None:
                continue
            title = f"{clock['label']} to claim ${r.amount_cents / 100:,.2f} in {r.county} County"
            kind = f"unclaimed_{m}"
            if _sent(session, user.id, kind, None, title=title):
                continue
            session.add(Notification(user_id=user.id, kind=kind, title=title,
                                     body=f"You haven't started this claim yet. The last day is "
                                          f"{clock['deadline']:%B %-d, %Y}; after that, {clock['if_missed'][0].lower()}"
                                          f"{clock['if_missed'][1:]}"))
            sent += 1
    return sent
