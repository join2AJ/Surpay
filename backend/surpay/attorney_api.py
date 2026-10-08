"""Partner attorney endpoints: apply, get verified, receive cases for your counties, report progress."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from . import attorneys, claims, config, crypto
from .deps import CurrentUser, DbSession, encrypt_image
from .legal import legal_basis
from .models import AttorneyProfile, Claim, ClaimEvent, User
from .schemas import AttorneyApplyIn, AttorneyProfileOut, CaseDeclineIn, CaseOut, CaseStatusIn

router = APIRouter(prefix="/attorney", tags=["attorney"])

TERMS_VERSION = "attorney-template-2026-10"


def terms_text(state: str) -> str:
    """TEMPLATE: have ethics counsel in each state review the arrangement and this text."""
    fee = config.attorney_fee_for(state) / 100
    return f"""SURPAY PARTNER ATTORNEY TERMS ({TERMS_VERSION}, pending legal review)

1. Cases. Surpay offers you surplus-funds claims for verified clients in the counties you serve. You may accept or decline any case. Please respond within 2 business days; unanswered offers may be reassigned.

2. Your client. On accepting, you represent the client, not Surpay. You exercise independent professional judgment; Surpay does not direct your legal work.

3. Payment. Surpay pays you ${fee:,.2f} per case, due when the case is finished (funds released or claim denied).

4. Your duties. Keep an active license in good standing and malpractice insurance; file promptly; keep the client informed; update each case's status in the app (filed, approved, paid or denied) so the client can follow it.

5. Confidentiality. Client identity documents and details are for this case only. Do not copy, share or use them for anything else.

6. Verification. Surpay verifies your bar license before sending cases and may suspend access if your license status changes.
"""


def _profile_out(a: AttorneyProfile) -> AttorneyProfileOut:
    return AttorneyProfileOut(
        full_name=a.full_name, bar_state=a.bar_state, bar_number=a.bar_number, firm=a.firm, phone=a.phone,
        office_address=a.office_address, counties=a.counties or [], status=a.status, review_note=a.review_note,
        fee_per_case_cents=config.attorney_fee_for(a.bar_state), terms=terms_text(a.bar_state),
    )


def _require_attorney(user: User, approved: bool = True) -> AttorneyProfile:
    if user.role != "attorney":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for partner attorneys")
    a = user.attorney
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Apply first")
    if approved and a.status != "approved":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your bar license is still being verified")
    return a


@router.get("/terms")
def get_terms(state: str) -> dict:
    return {"version": TERMS_VERSION, "text": terms_text(state), "fee_per_case_cents": config.attorney_fee_for(state)}


@router.post("/apply", response_model=AttorneyProfileOut)
def apply(body: AttorneyApplyIn, user: CurrentUser, session: DbSession):
    if user.role != "attorney":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Create an attorney account to apply")
    if not body.accept_terms:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please accept the partner terms")
    if user.attorney is not None and user.attorney.status != "rejected":
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already applied")
    if user.attorney is not None:
        session.delete(user.attorney)
        session.flush()
    user.attorney = AttorneyProfile(
        full_name=body.full_name.strip(), bar_state=body.bar_state, bar_number=body.bar_number.strip(),
        firm=body.firm.strip(), phone=body.phone.strip(), office_address=body.office_address.strip(),
        counties=sorted({c.strip() for c in body.counties if c.strip()}),
        bar_card=encrypt_image(body.bar_card_b64, "Bar card"),
    )
    session.commit()
    return _profile_out(user.attorney)


@router.get("/me", response_model=AttorneyProfileOut | None)
def me(user: CurrentUser):
    if user.role != "attorney":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for partner attorneys")
    return _profile_out(user.attorney) if user.attorney else None


def case_out(c: Claim, full: bool) -> CaseOut:
    r = c.record
    out = CaseOut(
        id=c.id, assignment_status=c.assignment_status, status=c.status, county=r.county, state=r.state,
        reference=r.reference, sale_type=r.sale_type, sale_date=r.sale_date, amount_cents=r.amount_cents,
        fee_cents=c.attorney_fee_cents, payout_status=c.payout_status, assigned_at=c.assigned_at,
        accepted_at=c.accepted_at, source_url=r.source_url, legal=legal_basis(r.state),
    )
    if full:
        u, i = c.user, c.user.identity
        out.claimant = {
            "name": i.legal_name if i else u.full_name, "email": u.email, "phone": i.phone if i else u.phone,
            "date_of_birth": i.date_of_birth.isoformat() if i else None,
            "current_address": f"{i.street}, {i.city}, {i.state} {i.zip}" if i else "",
            "other_names": u.other_names or [], "ssn_last4": i.ssn_last4 if i else "",
            "id_type": i.id_type if i else "", "has_id_back": bool(i and i.id_back),
            "homes": [f"{a.street}, {a.city}, {a.state} {a.zip} ({a.county})" for a in u.addresses],
        }
        a = c.agreement
        out.agreement = None if a is None else {
            "text": a.text, "signature_name": a.signature_name, "signed_at": a.signed_at.isoformat(),
            "fee_pct": a.fee_pct, "version": a.version,
        }
        out.record = {"owner_name": r.owner_name, "owner_address": r.owner_address, "raw": r.raw}
        out.history = [{"status": e.status, "note": e.note, "at": e.created_at.isoformat()} for e in c.events]
    return out


def _my_case(user: User, session, case_id: int) -> Claim:
    c = session.get(Claim, case_id)
    if c is None or c.attorney_id != user.id or c.assignment_status not in ("offered", "accepted"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return c


@router.get("/cases", response_model=list[CaseOut])
def my_cases(user: CurrentUser, session: DbSession):
    _require_attorney(user)
    rows = session.scalars(
        select(Claim).where(Claim.attorney_id == user.id, Claim.assignment_status.in_(("offered", "accepted")))
        .order_by(Claim.assigned_at.desc())
    )
    return [case_out(c, full=c.assignment_status == "accepted") for c in rows]


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: int, user: CurrentUser, session: DbSession):
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    return case_out(c, full=c.assignment_status == "accepted")


@router.post("/cases/{case_id}/accept", response_model=CaseOut)
def accept_case(case_id: int, user: CurrentUser, session: DbSession):
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        c.assignment_status = "accepted"
        c.accepted_at = datetime.now(timezone.utc)
        c.events.append(ClaimEvent(status=c.status, note=f"Attorney {user.attorney.full_name} took your case",
                                          created_at=datetime.now(timezone.utc)))
        session.commit()
    return case_out(c, full=True)


@router.post("/cases/{case_id}/decline")
def decline_case(case_id: int, body: CaseDeclineIn, user: CurrentUser, session: DbSession) -> dict:
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status == "accepted" and c.status != attorneys.READY:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already filed; contact Surpay to hand it over")
    attorneys.decline(session, c, user.id)
    session.commit()
    return {"ok": True}


@router.post("/cases/{case_id}/status", response_model=CaseOut)
def update_case(case_id: int, body: CaseStatusIn, user: CurrentUser, session: DbSession):
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Accept the case first")
    if attorneys.is_closed(c):
        raise HTTPException(status.HTTP_409_CONFLICT, "This case is already closed")
    claims.set_status(c, body.status, body.note)
    attorneys.settle_payout(c)
    session.commit()
    return case_out(c, full=True)


@router.get("/cases/{case_id}/documents/{kind}")
def case_document(case_id: int, kind: str, user: CurrentUser, session: DbSession):
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accept the case to see documents")
    i = c.user.identity
    if i is None or kind not in ("id_front", "id_back", "selfie") or getattr(i, kind) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not available")
    data = crypto.decrypt(getattr(i, kind))
    media = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return Response(data, media_type=media, headers={"Cache-Control": "no-store"})
