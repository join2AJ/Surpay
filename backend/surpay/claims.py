"""The claim process: its steps, how long each usually takes, and moving a claim through them.

Step estimates are deliberately wide. County and court timing varies a lot, and everything
shown to claimants carries the ESTIMATE_DISCLAIMER.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import config
from .models import Claim, ClaimEvent, User


@dataclass(frozen=True)
class Step:
    status: str
    title: str
    description: str
    # Usual days from the previous step finishing to this one finishing: (fastest, slowest).
    days: tuple[int, int]


STEPS: list[Step] = [
    Step("requested", "Claim started",
         "You asked us to recover this surplus for you.", (0, 0)),
    Step("identity_submitted", "Identity submitted",
         "Your ID, a selfie and your details. Takes about 5 minutes in the app.", (0, 0)),
    Step("agreement_signed", "Agreement signed",
         "You e-sign the contingency agreement. No fee unless the money is recovered.", (0, 0)),
    Step("identity_verified", "Identity verified",
         "Our team checks your ID against the county record. Usually 1–2 business days.", (1, 3)),
    Step("filed", "Claim filed",
         "A licensed attorney in the county's state prepares and files your claim with the county "
         "or court. Usually 1–3 weeks.", (7, 21)),
    Step("approved", "Approved by the county or court",
         "The county reviews the claim; many courts hold a short hearing. Usually 1–4 months, "
         "longer if another party also claims the funds.", (30, 120)),
    Step("paid", "Money released",
         "The county or court releases the funds and you receive your share. Usually 2–6 weeks "
         "after approval.", (14, 42)),
]
ORDER = [s.status for s in STEPS]
TERMINAL = {"denied", "withdrawn"}
ALL_STATUSES = ORDER + sorted(TERMINAL)

ESTIMATE_DISCLAIMER = (
    "All amounts and dates are approximate estimates, not a promise or guarantee. The final "
    "amount depends on the county or court, other lienholders who may claim part of the funds, "
    "and fees and costs. Timing depends on the county, the court and your documents."
)

AGREEMENT_VERSION = "template-2026-10"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite drops the timezone


def set_status(claim: Claim, status: str, note: str = "") -> None:
    """Move a claim to `status` and record it in the claim's history."""
    if status not in ALL_STATUSES:
        raise ValueError(f"Unknown status {status!r}")
    claim.status = status
    claim.events.append(ClaimEvent(status=status, note=note, created_at=_now()))


def advance(claim: Claim, status: str, note: str = "") -> bool:
    """Move forward to `status` if the claim hasn't reached it yet. Returns True if it moved."""
    if claim.status in TERMINAL or ORDER.index(status) <= ORDER.index(claim.status):
        return False
    set_status(claim, status, note)
    return True


def new_claim(session: Session, user: User, record_id: int) -> Claim:
    claim = Claim(user_id=user.id, record_id=record_id, status="requested")
    set_status(claim, "requested")
    session.add(claim)
    sync_with_identity(claim, user)
    return claim


def sync_with_identity(claim: Claim, user: User) -> None:
    """Carry the user's identity progress over to a claim (identity is shared by all claims)."""
    ident = user.identity
    if ident is None or ident.review_status == "rejected":
        return
    advance(claim, "identity_submitted", "Using the identity already on file")
    if ident.review_status == "approved" and claim.status == "agreement_signed":
        advance(claim, "identity_verified")


def next_action(claim: Claim) -> str | None:
    """What the claimant must do next in the app, if anything."""
    if claim.status == "requested":
        return "verify_identity"
    if claim.status == "identity_submitted":
        return "sign_agreement"
    return None


def timeline(claim: Claim) -> list[dict]:
    """Every step with its state and, for steps still ahead, an estimated date window."""
    reached = {e.status: _aware(e.created_at) for e in claim.events}
    current = ORDER.index(claim.status) if claim.status in ORDER else None
    out = []
    lo = hi = None  # running estimate window
    for i, step in enumerate(STEPS):
        done_at = reached.get(step.status)
        if claim.status in TERMINAL:
            state = "done" if done_at else "stopped"
        elif current is not None and i <= current:
            state = "done"
        elif current is not None and i == current + 1:
            state = "current"
        else:
            state = "upcoming"

        est_start = est_end = None
        if state == "done":
            lo = hi = done_at or _now()
        elif state in ("current", "upcoming"):
            base_lo, base_hi = (lo or _now()), (hi or _now())
            # A step that's waiting can't finish in the past.
            lo = max(base_lo + timedelta(days=step.days[0]), _now())
            hi = max(base_hi + timedelta(days=step.days[1]), lo)
            est_start, est_end = lo, hi
        out.append({
            "status": step.status, "title": step.title, "description": step.description,
            "state": state, "completed_at": done_at if state == "done" else None,
            "estimate_start": est_start.date() if est_start else None,
            "estimate_end": est_end.date() if est_end else None,
        })
    return out


def agreement_text(claim: Claim, user: User) -> str:
    """The contingency agreement shown to and signed by the claimant.

    TEMPLATE: have a licensed attorney in each state you operate in review and replace this
    before real claims are signed. Fee caps and required wording differ by state.
    """
    r = claim.record
    fee = config.fee_pct_for(r.state)
    sale_date = r.sale_date.strftime("%B %d, %Y") if r.sale_date else "the date of sale"
    return f"""SURPLUS FUNDS RECOVERY — CONTINGENCY FEE AGREEMENT
(Template version {AGREEMENT_VERSION}, pending attorney review)

Claimant: {user.full_name}
Funds: surplus from the {r.sale_type.replace('_', ' ')} on {sale_date}, {r.county} County, {r.state} ({r.reference})
Amount the county reports holding: ${r.amount_cents / 100:,.2f} (approximate; may change)

1. What Surpay does. Surpay arranges for a licensed attorney in {r.state} to prepare and file a claim for these funds on your behalf, and keeps you updated in the app. Surpay is not a law firm and does not give legal advice.

2. Fee. You pay nothing upfront. If funds are recovered for you, the fee is {fee:g}% of the amount actually recovered, and never more than the maximum allowed by {r.state} law. If nothing is recovered, you owe nothing.

3. You can do this yourself. You have the right to claim these funds directly from the county or court without paying anyone.

4. Estimates. Amounts and timelines shown in the app are approximate estimates, not guarantees. Other lienholders may have a right to part of the funds.

5. Cancellation. You may cancel this agreement within 3 business days of signing by contacting Surpay, at no cost. After that, you may still withdraw, but costs already incurred by the attorney may apply where state law allows.

6. Your information. You authorize Surpay and its partner attorney to use the identity documents and details you provided only to verify your identity and pursue this claim.

7. Electronic signature. By typing your name and tapping Sign, you agree that your electronic signature has the same effect as a handwritten signature.
"""
