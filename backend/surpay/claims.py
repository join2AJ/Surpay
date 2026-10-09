"""The claim process: its steps, how long each usually takes, and moving a claim through them.

Step estimates are deliberately wide. County and court timing varies a lot, and everything
shown to claimants carries the ESTIMATE_DISCLAIMER.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, object_session

from . import config
from .models import Claim, ClaimEvent, Notification, User


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
         "You sign the contingency agreement in the app. No fee unless money is recovered.", (0, 0)),
    Step("identity_verified", "Identity verified",
         "Our team checks your ID against the county record. Usually 1 to 2 business days.", (1, 3)),
    Step("attorney_assigned", "Attorney assigned",
         "A licensed attorney who practises in that county accepts your case. You can message them "
         "in the app from here on.", (1, 7)),
    Step("filed", "Claim filed",
         "Your attorney prepares the claim with your documents and files it with the county or "
         "court. Usually 1 to 3 weeks.", (7, 21)),
    Step("hearing_pending", "Waiting for the county or court",
         "The claim is with the county or court. Many courts set a hearing date; some counties "
         "review the paperwork without one.", (3, 30)),
    Step("approved", "Hearing held and claim approved",
         "The judge or county officer approves the claim and orders the money paid out. Usually "
         "1 to 4 months after filing, longer if someone else also claims the funds.", (30, 120)),
    Step("paid", "Money released",
         "The county or court releases the funds and you receive your share. Usually 2 to 6 weeks "
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

AGREEMENT_VERSION = "2026-10-B"

# What the claimant is told when their claim reaches a step (phone notification + in-app).
_UPDATES = {
    "identity_verified": ("claim_update", "Your identity is verified",
                          "We're now matching your claim with a licensed attorney in {county}."),
    "attorney_assigned": ("claim_update", "An attorney has taken your case",
                          "{attorney} will file your claim. You can message them in the app."),
    "filed": ("claim_update", "Your claim has been filed",
              "Your attorney filed the claim for {amount} with {county}."),
    "hearing_pending": ("claim_update", "Waiting for the county or court",
                        "Your claim is with {county} for review or a hearing."),
    "approved": ("claim_update", "Your claim was approved",
                 "The county or court approved your claim. Payment usually follows in 2 to 6 weeks."),
    "paid": ("money_released", "Money released",
             "{county} has released the funds for your claim. Your attorney will confirm your payment."),
    "denied": ("claim_update", "Update on your claim",
               "The county or court did not approve this claim. Open the app for details."),
    "requested": ("claim_update", "Please resubmit your ID",
                  "We couldn't verify your ID. Open the app to upload it again."),
}


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
    _notify_claimant(claim, status, note)


def _notify_claimant(claim: Claim, status: str, note: str) -> None:
    session = object_session(claim)
    if session is None or status not in _UPDATES or claim.id is None:
        return
    if status == "requested" and not note:
        return  # a brand-new claim, not a resubmission request
    kind, title, body = _UPDATES[status]
    r = claim.record
    lawyer = claim.attorney.attorney.full_name if claim.attorney and claim.attorney.attorney else "Your attorney"
    body = body.format(county=f"{r.county} County, {r.state}", amount=f"${r.amount_cents / 100:,.2f}",
                       attorney=lawyer)
    if note and status not in ("requested",):
        body = f"{body} Note: {note}"
    session.add(Notification(user_id=claim.user_id, kind=kind, title=title, body=body, claim_id=claim.id))


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
    a = claim.agreement
    if a is not None and claim.status == "identity_submitted":
        # Signed before an ID resubmission: still valid if it's in the same verified name,
        # otherwise they sign again in their new name.
        if names_match(a.signature_name, ident.legal_name):
            advance(claim, "agreement_signed", "Using the agreement already signed")
        else:
            claim.agreement = None  # delete-orphan removes the old one; the audit log keeps its record
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


def names_match(typed: str, legal: str) -> bool:
    """A typed signature matches the verified legal name, ignoring case, spacing and punctuation."""
    def norm(x: str) -> str:
        return " ".join("".join(ch for ch in x.lower() if ch.isalnum() or ch.isspace()).split())
    return bool(norm(typed)) and norm(typed) == norm(legal)


def agreement_text(claim: Claim, user: User, fee_pct: float) -> str:
    """The contingency agreement shown to and signed by the claimant.

    Have a licensed attorney in each state you operate in review this wording before real
    claims are signed; fee limits and required notices differ by state.
    """
    r = claim.record
    ident = user.identity
    legal_name = ident.legal_name if ident else user.full_name
    sale_date = r.sale_date.strftime("%B %-d, %Y") if r.sale_date else "the date of sale"
    sale = "tax sale" if r.sale_type == "tax_sale" else "foreclosure sale"
    rel = claim.relative
    if rel is not None:
        capacity = {"heir": f"as an heir of {rel.full_name}, deceased",
                    "power_of_attorney": f"as attorney-in-fact for {rel.full_name}",
                    "guardian": f"as court-appointed guardian of {rel.full_name}"}.get(rel.basis, "")
        owner_line = f"Former owner: {rel.full_name} (the Claimant acts {capacity})"
    else:
        owner_line = f"Former owner: {legal_name}"
    company = config.COMPANY_NAME
    return f"""SURPLUS FUNDS RECOVERY AGREEMENT
Agreement No. SP-{claim.id:06d}   Version {AGREEMENT_VERSION}

This Agreement is made between {legal_name} ("Claimant") and {company} ("{company}").

PROPERTY AND FUNDS
County: {r.county} County, {r.state}
Reference: {r.reference}
{owner_line}
Sale: {sale} held on {sale_date}
Amount reported by the county or court: ${r.amount_cents / 100:,.2f}

1. PURPOSE
The Claimant wishes to recover the surplus funds described above. {company} will arrange for an independent attorney licensed in {r.state} (the "Attorney") to prepare and file the claim on the Claimant's behalf, and will provide the Claimant with case updates through the {company} app.

2. ROLE OF {company.upper()}
{company} is a technology platform that connects claimants with independent attorneys and provides case tracking. {company} is not a law firm, does not provide legal advice, and does not represent the Claimant before any court or government office. {company} acts only as a facilitator.

3. THE ATTORNEY
The Attorney represents the Claimant and is solely responsible for the legal work, including the preparation, accuracy and filing of the claim and any court appearance. The Attorney exercises independent professional judgment and is not directed by {company}. The Claimant may ask for a different attorney at any time before the claim is filed.
3.1 Payment of the Attorney by {company}. {company} pays the Attorney for this claim out of the fee in section 4. The Claimant consents to this arrangement. {company} will not interfere with the Attorney's independent professional judgment or with the attorney-client relationship, and information relating to the representation remains confidential between the Claimant and the Attorney except as needed to administer this Agreement. The Attorney will confirm the scope of the representation to the Claimant.

4. FEE
4.1 No fee is payable unless funds are recovered.
4.2 If funds are recovered, the Claimant will pay a fee of {fee_pct:g}% of the amount actually paid out on the claim. The fee will not exceed the maximum permitted by the law of {r.state}; if a lower limit applies, the lower limit is the fee.
4.3 The fee covers the Attorney's work on the claim. The Claimant pays no separate legal fees or filing costs for this claim.
4.4 If nothing is recovered, the Claimant owes nothing.

5. CLAIMANT'S RIGHT TO CLAIM DIRECTLY
The Claimant understands that they may claim these funds directly from the county or court without using {company} or paying any fee.

6. CLAIMANT'S STATEMENTS
The Claimant confirms that the information and documents they have provided are true, complete and their own, and that they are entitled to claim these funds{' in the capacity stated above' if rel else ''}. The Claimant is responsible for any loss caused by false or incomplete information.

7. NO GUARANTEE
Amounts and timelines shown in the app are estimates. The county or court decides whether and how much is paid. Other parties, such as lienholders or co-owners, may be entitled to part of the funds.

8. LIMITATION OF LIABILITY
To the fullest extent permitted by law, {company} is not liable for the outcome of the claim, for any act or omission of the Attorney, the county, the court or any other party, or for any indirect or consequential loss. {company}'s total liability under this Agreement will not exceed the fee it actually receives for this claim. Nothing in this Agreement limits liability that cannot be limited by law.

9. CANCELLATION
The Claimant may cancel this Agreement by written notice to {config.SUPPORT_CONTACT} within three (3) business days after signing, at no cost. After that, the Claimant may end the Agreement by written notice before the claim is filed. Once the claim is filed, the fee in section 4 applies to any funds later paid out on it.

10. PERSONAL INFORMATION
The Claimant authorises {company} and the Attorney to use their identity documents and personal details only to verify their identity and pursue this claim, as described in the {company} Privacy Notice. Communications about the claim take place in the app and are kept as part of the case record.

11. ELECTRONIC SIGNATURE AND RECORDS
The Claimant agrees to sign electronically under the U.S. Electronic Signatures in Global and National Commerce Act (15 U.S.C. 7001 et seq.) and the Uniform Electronic Transactions Act as adopted in {r.state}. The Claimant's drawn signature, typed legal name, the time of signing, IP address and device identifier are recorded with a fingerprint (SHA-256) of this text as evidence of signing.
11.1 Consumer disclosures. The Claimant may (a) receive a paper copy of this Agreement free of charge by writing to {config.SUPPORT_CONTACT}; (b) withdraw consent to receive records electronically at any time by writing to that address, without affecting the validity of this Agreement; and (c) access these records using the {company} app on a current Android device, or by asking for a PDF copy. This consent applies to this Agreement and to records about this claim.

12. GOVERNING LAW
This Agreement is governed by the law of the State of {r.state}.

13. ENTIRE AGREEMENT
This is the entire agreement between the parties about this claim. A copy is available to the Claimant in the app at any time.
"""
