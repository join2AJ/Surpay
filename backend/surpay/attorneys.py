"""Matching verified claims to partner attorneys who serve the county."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .claims import TERMINAL
from .models import AttorneyProfile, Claim

# Steps after which a claim is ready for (or already with) an attorney.
READY = "identity_verified"
OPEN_STATUSES = ("identity_verified", "filed", "approved")
ATTORNEY_STATUSES = ("filed", "approved", "paid", "denied")


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
    ]
    if not candidates:
        return None
    chosen = min(candidates, key=lambda a: (_open_load(session, a.user_id), a.id))
    claim.attorney_id = chosen.user_id
    claim.assignment_status = "offered"
    claim.assigned_at = datetime.now(timezone.utc)
    claim.accepted_at = None
    claim.attorney_fee_cents = config.attorney_fee_for(r.state)
    return chosen


def assign_ready(session: Session) -> int:
    """Offer every verified, unassigned claim to an attorney. Safe to call any time."""
    waiting = session.scalars(
        select(Claim).where(Claim.status == READY, Claim.assignment_status == "")
    ).all()
    offered = sum(1 for c in waiting if offer(session, c))
    session.commit()
    return offered


def decline(session: Session, claim: Claim, attorney_user_id: int) -> None:
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
