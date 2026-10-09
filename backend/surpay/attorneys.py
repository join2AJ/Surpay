"""Matching verified claims to partner attorneys who serve the county."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .claims import TERMINAL
from .models import AttorneyProfile, Claim, ClaimEvent, Notification

# Steps after which a claim is ready for (or already with) an attorney.
READY = "identity_verified"
OPEN_STATUSES = ("identity_verified", "attorney_assigned", "filed", "hearing_pending", "approved")
ATTORNEY_STATUSES = ("filed", "hearing_pending", "approved", "paid", "denied")
# An attorney can hand a case back until they've filed it.
RETURNABLE = ("identity_verified", "attorney_assigned")
# What an attorney may report next from each stage. Steps can't be skipped or reversed;
# "paid" needs an approval first.
NEXT_STATUS = {
    "identity_verified": ("filed",),
    "attorney_assigned": ("filed",),
    "filed": ("hearing_pending", "approved", "denied"),
    "hearing_pending": ("approved", "denied"),
    "approved": ("paid", "denied"),
}
# Offers not answered within this many days go to the next attorney.
OFFER_EXPIRY_DAYS = 3


def _open_load(session: Session, attorney_user_id: int) -> int:
    return session.scalar(
        select(func.count()).select_from(Claim).where(
            Claim.attorney_id == attorney_user_id,
            Claim.assignment_status.in_(("offered", "accepted")),
            Claim.status.in_(OPEN_STATUSES),
        )
    ) or 0


def offer(session: Session, claim: Claim) -> AttorneyProfile | None:
    """Offer the claim to the least-busy approved attorney serving its county. None if nobody does."""
    r = claim.record
    declined = set(claim.declined_by or [])
    candidates = [
        a for a in session.scalars(select(AttorneyProfile).where(AttorneyProfile.status == "approved"))
        if a.serves(r.county, r.state) and a.user_id not in declined and a.user_id != claim.user_id
        and a.user.deletion_requested_at is None
    ]
    if not candidates:
        return None
    chosen = min(candidates, key=lambda a: (_open_load(session, a.user_id), a.id))
    claim.attorney_id = chosen.user_id
    claim.assignment_status = "offered"
    claim.assigned_at = datetime.now(timezone.utc)
    claim.accepted_at = None
    claim.attorney_fee_cents = config.attorney_fee_for(r.state)
    session.add(Notification(
        user_id=chosen.user_id, kind="case_offer", title="New case offered",
        body=f"${r.amount_cents / 100:,.2f} surplus in {r.county} County, {r.state}. Accept or decline in the app.",
        claim_id=claim.id))
    return chosen


def assign_ready(session: Session) -> int:
    """Offer every verified, unassigned claim to an attorney. Safe to call any time."""
    waiting = session.scalars(
        select(Claim).where(Claim.status == READY, Claim.assignment_status == "")
    ).all()
    offered = sum(1 for c in waiting if offer(session, c))
    session.commit()
    return offered


def decline(session: Session, claim: Claim, attorney_user_id: int, reason: str = "") -> None:
    was_accepted = claim.assignment_status == "accepted"
    if claim.status == "attorney_assigned":
        claim.status = READY  # back in the queue; the client keeps their history
    if was_accepted:
        note = reason or "Your attorney handed the case back. We're finding you another attorney."
        claim.events.append(ClaimEvent(status=claim.status, note=note, created_at=datetime.now(timezone.utc)))
        session.add(Notification(user_id=claim.user_id, kind="claim_update", title="We're finding you a new attorney",
                                 body=note, claim_id=claim.id))
    claim.declined_by = [*(claim.declined_by or []), attorney_user_id]
    claim.attorney_id = None
    claim.assignment_status = ""
    claim.assigned_at = None
    offer(session, claim)


def settle_payout(claim: Claim) -> None:
    """The attorney's per-case fee falls due once the case is finished either way."""
    if claim.attorney_id and claim.status in ("paid", "denied") and claim.payout_status == "":
        claim.payout_status = "due"


def is_closed(claim: Claim) -> bool:
    return claim.status in ("paid", "denied", *TERMINAL)


def release(session: Session, claim: Claim) -> None:
    """Take a closed or withdrawn claim away from its attorney's case list (offers only)."""
    if claim.assignment_status == "offered":
        claim.attorney_id = None
        claim.assignment_status = ""
        claim.assigned_at = None


def expire_offers(session: Session) -> int:
    """Pass unanswered offers to the next attorney (run daily)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=OFFER_EXPIRY_DAYS)
    stale = [c for c in session.scalars(select(Claim).where(Claim.assignment_status == "offered"))
             if c.assigned_at is not None and (c.assigned_at if c.assigned_at.tzinfo else
                                               c.assigned_at.replace(tzinfo=timezone.utc)) < cutoff]
    for c in stale:
        decline(session, c, c.attorney_id)
    session.commit()
    return len(stale)
