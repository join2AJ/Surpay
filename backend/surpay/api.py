from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import attorneys, claims, config, crypto
from .attorney_api import router as attorney_router
from .auth import create_token, hash_password, verify_password
from .claims import ESTIMATE_DISCLAIMER
from .db import init_db
from .demo import reset_demo_user
from .deps import Admin, CurrentUser, DbSession, encrypt_image
from .legal import legal_basis
from .matching import find_matches
from .models import (
    Agreement, AttorneyProfile, Claim, ClaimEvent, CountySource, IdentityVerification, PreviousAddress,
    SurplusRecord, User,
)
from .schemas import (
    AddressOut, AdminAttorneyIn, AdminIdentityIn, AttorneyPublic, AdminStatusIn, AgreementOut, ClaimIn, ClaimOut, CoverageOut, IdentityIn,
    LoginIn, MatchesOut, MatchOut, MatchPreviewOut, ProfileIn, ProfileOut, SignIn, SignupIn, TokenOut,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Surpay API", version="0.1.0", lifespan=lifespan)
app.include_router(attorney_router)



def _identity_status(user: User) -> str | None:
    return user.identity.review_status if user.identity is not None else None


def _name_locked(user: User) -> bool:
    return _identity_status(user) in ("pending", "approved")


def _profile(user: User) -> ProfileOut:
    ident = user.identity
    return ProfileOut(
        id=user.id, email=user.email, full_name=user.full_name,
        other_names=user.other_names or [], phone=user.phone,
        addresses=[AddressOut(id=a.id, street=a.street, city=a.city, state=a.state, zip=a.zip,
                              county=a.county) for a in user.addresses],
        identity_status=_identity_status(user),
        identity_note=ident.review_note if ident is not None and ident.review_status == "rejected" else "",
        name_locked=_name_locked(user),
        role=user.role,
    )


def require_verified(user: User) -> None:
    """Amounts and record details are only for people whose ID we've approved.

    This is what stops a broker from creating an account and typing in a client's name.
    """
    status_ = _identity_status(user)
    if status_ != "approved":
        detail = {None: "Verify your identity to see your results",
                  "rejected": "Please resubmit your ID to see your results"}.get(
            status_, "Your identity is being verified. Results unlock once it's approved")
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail)


def _covered_counties(session: Session) -> list[str]:
    rows = session.execute(
        select(SurplusRecord.county, SurplusRecord.state)
        .where(SurplusRecord.status == "listed").distinct()
        .order_by(SurplusRecord.state, SurplusRecord.county)
    ).all()
    return [f"{c} County, {s}" for c, s in rows]


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/coverage", response_model=CoverageOut)
def coverage(session: DbSession):
    """Public, aggregate-only: how much we're tracking and where. No names."""
    count, total = session.execute(
        select(func.count(), func.coalesce(func.sum(SurplusRecord.amount_cents), 0))
        .where(SurplusRecord.status == "listed")
    ).one()
    return CoverageOut(records=count, total_amount_cents=total, counties=_covered_counties(session),
                       demo_login=config.DEMO_ENABLED)


@app.post("/auth/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, session: DbSession):
    user = User(email=body.email.lower(), password_hash=hash_password(body.password),
                full_name=body.full_name.strip(), phone=body.phone, other_names=[], role=body.role)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from None
    return TokenOut(token=create_token(user.id), user=_profile(user))


@app.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, session: DbSession):
    user = session.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return TokenOut(token=create_token(user.id), user=_profile(user))


@app.post("/auth/demo", response_model=TokenOut)
def demo_login(session: DbSession):
    """One-tap sign-in to a shared, fictional test account. Only when SURPAY_SEED_DEMO=true."""
    if not config.DEMO_ENABLED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo login is turned off on this server")
    user = reset_demo_user(session)
    return TokenOut(token=create_token(user.id), user=_profile(user))


@app.get("/me", response_model=ProfileOut)
def get_me(user: CurrentUser):
    return _profile(user)


@app.put("/me", response_model=ProfileOut)
def update_me(body: ProfileIn, user: CurrentUser, session: DbSession):
    other_names = [n.strip() for n in body.other_names if n.strip()]
    if _name_locked(user) and (body.full_name.strip() != user.full_name or other_names != (user.other_names or [])):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Your name is locked to your verified ID. Contact support to change it.")
    user.full_name = body.full_name.strip()
    user.other_names = other_names
    user.phone = body.phone
    user.addresses = [PreviousAddress(**a.model_dump()) for a in body.addresses]
    session.add(user)
    session.commit()
    session.refresh(user)
    return _profile(user)


@app.get("/me/matches/preview", response_model=MatchPreviewOut)
def my_matches_preview(user: CurrentUser, session: DbSession):
    """While ID is under review: only how many possible records, never amounts or details."""
    if user.identity is None or user.identity.review_status == "rejected":
        return MatchPreviewOut(identity_status=_identity_status(user), possible_matches=0)
    return MatchPreviewOut(identity_status=_identity_status(user), possible_matches=len(find_matches(session, user)))


@app.get("/me/matches", response_model=MatchesOut)
def my_matches(user: CurrentUser, session: DbSession):
    require_verified(user)
    claim_status = {c.record_id: c.status for c in user.claims}
    out = []
    for m in find_matches(session, user):
        r = m.record
        pct = config.fee_pct_for(r.state)
        fee = round(r.amount_cents * pct / 100)
        out.append(MatchOut(
            record_id=r.id, confidence=m.confidence, address_matched=m.address_matched,
            state=r.state, county=r.county, sale_type=r.sale_type, reference=r.reference,
            owner_name=r.owner_name, owner_address=r.owner_address, amount_cents=r.amount_cents,
            fee_pct=pct, estimated_fee_cents=fee, estimated_net_cents=r.amount_cents - fee,
            sale_date=r.sale_date, source_url=r.source_url, last_seen=r.last_seen,
            claim_status=claim_status.get(r.id), legal=legal_basis(r.state),
        ))
    searched = session.scalar(select(func.count()).select_from(SurplusRecord)
                              .where(SurplusRecord.status == "listed"))
    return MatchesOut(
        matches=out,
        total_amount_cents=sum(m.amount_cents for m in out),
        total_estimated_net_cents=sum(m.estimated_net_cents for m in out),
        records_searched=searched,
        counties_covered=_covered_counties(session),
        disclaimer=ESTIMATE_DISCLAIMER,
    )


def _net(record: SurplusRecord) -> int:
    return record.amount_cents - round(record.amount_cents * config.fee_pct_for(record.state) / 100)


def _claim_out(c: Claim) -> ClaimOut:
    r = c.record
    steps = claims.timeline(c)
    ends = [s for s in steps if s["estimate_end"]]
    ident = c.user.identity
    return ClaimOut(
        id=c.id, record_id=r.id, status=c.status, county=r.county, state=r.state,
        reference=r.reference, amount_cents=r.amount_cents, estimated_net_cents=_net(r),
        created_at=c.created_at, updated_at=c.updated_at,
        next_action=claims.next_action(c),
        identity_status=ident.review_status if ident else None,
        identity_note=ident.review_note if ident and ident.review_status == "rejected" else "",
        timeline=steps,
        estimated_completion_start=ends[-1]["estimate_start"] if ends else None,
        estimated_completion_end=ends[-1]["estimate_end"] if ends else None,
        disclaimer=ESTIMATE_DISCLAIMER,
        legal=legal_basis(r.state),
        attorney=_attorney_public(c),
    )


def _attorney_public(c: Claim) -> AttorneyPublic | None:
    a = c.attorney.attorney if c.attorney is not None and c.assignment_status == "accepted" else None
    if a is None:
        return None
    return AttorneyPublic(name=a.full_name, firm=a.firm, phone=a.phone, bar=f"{a.bar_state} Bar #{a.bar_number}")


def _my_claim(user: User, claim_id: int) -> Claim:
    claim = next((c for c in user.claims if c.id == claim_id), None)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    return claim


@app.post("/me/claims", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def start_claim(body: ClaimIn, user: CurrentUser, session: DbSession):
    require_verified(user)
    # Only allow claiming records the matcher actually linked to this user.
    if body.record_id not in {m.record.id for m in find_matches(session, user)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching record for your profile")
    existing = session.scalar(select(Claim).where(Claim.user_id == user.id, Claim.record_id == body.record_id))
    if existing:
        return _claim_out(existing)
    claim = claims.new_claim(session, user, body.record_id)
    session.commit()
    session.refresh(claim)
    return _claim_out(claim)


@app.get("/me/claims", response_model=list[ClaimOut])
def my_claims(user: CurrentUser):
    return [_claim_out(c) for c in sorted(user.claims, key=lambda c: c.created_at, reverse=True)]


@app.get("/me/claims/{claim_id}", response_model=ClaimOut)
def my_claim(claim_id: int, user: CurrentUser):
    return _claim_out(_my_claim(user, claim_id))


@app.post("/me/identity", response_model=list[ClaimOut])
def submit_identity(body: IdentityIn, user: CurrentUser, session: DbSession):
    """Submit ID for review. Shared by all of the user's claims; resubmit after a rejection."""
    if not body.consent:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please confirm the information is yours and correct")
    if user.identity is not None and user.identity.review_status != "rejected":
        raise HTTPException(status.HTTP_409_CONFLICT, "Your identity is already submitted")
    if user.identity is not None:  # replacing a rejected submission
        session.delete(user.identity)
        session.flush()
    user.other_names = [n.strip() for n in body.other_names if n.strip()]
    user.identity = IdentityVerification(
        legal_name=body.legal_name.strip(), date_of_birth=body.date_of_birth, ssn_last4=body.ssn_last4,
        phone=body.phone.strip(), street=body.street.strip(), city=body.city.strip(), state=body.state,
        zip=body.zip, id_type=body.id_type,
        id_front=encrypt_image(body.id_front_b64, "ID front"),
        id_back=encrypt_image(body.id_back_b64, "ID back") if body.id_back_b64 else None,
        selfie=encrypt_image(body.selfie_b64, "Selfie"),
    )
    for c in user.claims:
        claims.sync_with_identity(c, user)
    session.commit()
    session.refresh(user)
    return [_claim_out(c) for c in user.claims]


@app.get("/me/identity/status", response_model=ProfileOut)
def identity_status(user: CurrentUser):
    """Same as GET /me; the app polls this while waiting for review."""
    return _profile(user)


@app.get("/me/claims/{claim_id}/agreement", response_model=AgreementOut)
def get_agreement(claim_id: int, user: CurrentUser):
    claim = _my_claim(user, claim_id)
    a = claim.agreement
    if a:
        return AgreementOut(version=a.version, text=a.text, fee_pct=a.fee_pct, signed=True,
                            signature_name=a.signature_name, signed_at=a.signed_at)
    return AgreementOut(version=claims.AGREEMENT_VERSION, text=claims.agreement_text(claim, user),
                        fee_pct=config.fee_pct_for(claim.record.state), signed=False,
                        signature_name=None, signed_at=None)


@app.post("/me/claims/{claim_id}/agreement", response_model=ClaimOut)
def sign_agreement(claim_id: int, body: SignIn, request: Request, user: CurrentUser, session: DbSession):
    claim = _my_claim(user, claim_id)
    if claim.agreement is not None:
        return _claim_out(claim)
    if claim.status != "identity_submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Verify your identity before signing")
    if not body.agreed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please tick the box to agree")
    claim.agreement = Agreement(
        version=claims.AGREEMENT_VERSION, text=claims.agreement_text(claim, user),
        fee_pct=config.fee_pct_for(claim.record.state), signature_name=body.signature_name.strip(),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:255],
    )
    claims.advance(claim, "agreement_signed")
    claims.sync_with_identity(claim, user)
    session.commit()
    attorneys.assign_ready(session)
    session.refresh(claim)
    return _claim_out(claim)


@app.get("/counties")
def counties_in_state(state: str, session: DbSession) -> list[str]:
    """County names for one state, for the address form (e.g. ["Adams County", ...])."""
    return list(session.scalars(
        select(CountySource.county).where(CountySource.state == state.upper()).order_by(CountySource.county)
    ))


# --- Staff review (enabled by SURPAY_ADMIN_TOKEN) -------------------------------------------

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page():
    if not config.ADMIN_TOKEN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return HTMLResponse((Path(__file__).parent / "static" / "admin.html").read_text())


def _admin_claim(c: Claim) -> dict:
    u, i = c.user, c.user.identity
    return {
        **_claim_out(c).model_dump(mode="json"),
        "user": {"id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone,
                 "addresses": [AddressOut(id=a.id, street=a.street, city=a.city, state=a.state, zip=a.zip,
                                          county=a.county).model_dump() for a in u.addresses]},
        "owner_name": c.record.owner_name, "owner_address": c.record.owner_address,
        "identity": None if i is None else {
            "legal_name": i.legal_name, "date_of_birth": i.date_of_birth.isoformat(), "ssn_last4": i.ssn_last4,
            "phone": i.phone, "address": f"{i.street}, {i.city}, {i.state} {i.zip}", "id_type": i.id_type,
            "has_id_back": i.id_back is not None, "review_status": i.review_status,
            "review_note": i.review_note, "submitted_at": i.submitted_at.isoformat(),
        },
        "attorney": None if c.attorney is None or c.attorney.attorney is None else {
            "name": c.attorney.attorney.full_name, "firm": c.attorney.attorney.firm,
            "assignment_status": c.assignment_status, "fee_cents": c.attorney_fee_cents,
            "payout_status": c.payout_status,
        },
        "agreement": None if c.agreement is None else {
            "signature_name": c.agreement.signature_name, "signed_at": c.agreement.signed_at.isoformat(),
            "version": c.agreement.version, "ip_address": c.agreement.ip_address,
        },
        "history": [{"status": e.status, "note": e.note, "at": e.created_at.isoformat()} for e in c.events],
    }


@app.get("/admin/claims")
def admin_claims(_: Admin, session: DbSession) -> list[dict]:
    return [_admin_claim(c) for c in session.scalars(select(Claim).order_by(Claim.id.desc()))]


@app.get("/admin/identities")
def admin_identities(_: Admin, session: DbSession, review_status: str = "pending") -> list[dict]:
    """People waiting for ID review (or approved / rejected), oldest first, with what they listed."""
    rows = session.scalars(
        select(IdentityVerification).where(IdentityVerification.review_status == review_status)
        .order_by(IdentityVerification.submitted_at)
    )
    out = []
    for i in rows:
        u = i.user
        out.append({
            "user": {"id": u.id, "email": u.email, "full_name": u.full_name, "other_names": u.other_names or [],
                     "addresses": [AddressOut(id=a.id, street=a.street, city=a.city, state=a.state, zip=a.zip,
                                              county=a.county).model_dump() for a in u.addresses]},
            "identity": {
                "legal_name": i.legal_name, "date_of_birth": i.date_of_birth.isoformat(), "ssn_last4": i.ssn_last4,
                "phone": i.phone, "address": f"{i.street}, {i.city}, {i.state} {i.zip}", "id_type": i.id_type,
                "has_id_back": i.id_back is not None, "review_status": i.review_status,
                "review_note": i.review_note, "submitted_at": i.submitted_at.isoformat(),
            },
            "possible_matches": len(find_matches(session, u)),
        })
    return out


@app.get("/admin/users/{user_id}/documents/{kind}")
def admin_document(user_id: int, kind: str, _: Admin, session: DbSession):
    user = session.get(User, user_id)
    if user is None or user.identity is None or kind not in ("id_front", "id_back", "selfie"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    blob = getattr(user.identity, kind)
    if blob is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not provided")
    data = crypto.decrypt(blob)
    media = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return Response(data, media_type=media, headers={"Cache-Control": "no-store"})


@app.post("/admin/users/{user_id}/identity")
def admin_review_identity(user_id: int, body: AdminIdentityIn, _: Admin, session: DbSession) -> dict:
    user = session.get(User, user_id)
    if user is None or user.identity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No identity submitted")
    user.identity.review_status = body.decision
    user.identity.review_note = body.note
    user.identity.reviewed_at = datetime.now(timezone.utc)
    if body.decision == "approved":
        user.full_name = user.identity.legal_name  # searches use the verified name from now on
    for c in user.claims:
        if body.decision == "approved":
            claims.sync_with_identity(c, user)
        elif c.status in ("identity_submitted", "agreement_signed"):
            # Send them back to re-upload; a signed agreement stays on file.
            claims.set_status(c, "requested", f"ID needs to be resubmitted: {body.note}")
    session.commit()
    attorneys.assign_ready(session)
    return {"ok": True}


@app.post("/admin/claims/{claim_id}/status")
def admin_set_status(claim_id: int, body: AdminStatusIn, _: Admin, session: DbSession) -> dict:
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    try:
        claims.set_status(claim, body.status, body.note)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    attorneys.settle_payout(claim)
    session.commit()
    attorneys.assign_ready(session)
    return _admin_claim(claim)


@app.post("/admin/claims/{claim_id}/reassign")
def admin_reassign(claim_id: int, _: Admin, session: DbSession) -> dict:
    """Take the case away from its current attorney (e.g. no response) and offer it to the next."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    if claim.attorney_id:
        attorneys.decline(session, claim, claim.attorney_id)
    else:
        attorneys.offer(session, claim)
    session.commit()
    return _admin_claim(claim)


@app.post("/admin/claims/{claim_id}/payout")
def admin_payout(claim_id: int, _: Admin, session: DbSession) -> dict:
    """Record that the attorney's per-case fee has been paid."""
    claim = session.get(Claim, claim_id)
    if claim is None or claim.payout_status != "due":
        raise HTTPException(status.HTTP_409_CONFLICT, "No payout due on this claim")
    claim.payout_status = "paid"
    claim.events.append(ClaimEvent(status=claim.status, note="Attorney fee paid", created_at=datetime.now(timezone.utc)))
    session.commit()
    return _admin_claim(claim)


@app.get("/admin/attorneys")
def admin_attorneys(_: Admin, session: DbSession, review_status: str = "pending") -> list[dict]:
    rows = session.scalars(select(AttorneyProfile).where(AttorneyProfile.status == review_status)
                           .order_by(AttorneyProfile.created_at))
    out = []
    for a in rows:
        open_cases = session.scalar(select(func.count()).select_from(Claim).where(
            Claim.attorney_id == a.user_id, Claim.assignment_status.in_(("offered", "accepted")),
            Claim.status.in_(attorneys.OPEN_STATUSES)))
        out.append({
            "user_id": a.user_id, "email": a.user.email, "full_name": a.full_name, "bar_state": a.bar_state,
            "bar_number": a.bar_number, "firm": a.firm, "phone": a.phone, "office_address": a.office_address,
            "counties": a.counties, "status": a.status, "review_note": a.review_note,
            "applied_at": a.created_at.isoformat(), "open_cases": open_cases,
        })
    return out


@app.get("/admin/attorneys/{user_id}/bar-card")
def admin_bar_card(user_id: int, _: Admin, session: DbSession):
    user = session.get(User, user_id)
    if user is None or user.attorney is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    data = crypto.decrypt(user.attorney.bar_card)
    media = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return Response(data, media_type=media, headers={"Cache-Control": "no-store"})


@app.post("/admin/attorneys/{user_id}")
def admin_review_attorney(user_id: int, body: AdminAttorneyIn, _: Admin, session: DbSession) -> dict:
    user = session.get(User, user_id)
    if user is None or user.attorney is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No application")
    user.attorney.status = body.decision
    user.attorney.review_note = body.note
    user.attorney.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    offered = attorneys.assign_ready(session)  # cases waiting in their counties go out now
    return {"ok": True, "cases_offered": offered}
