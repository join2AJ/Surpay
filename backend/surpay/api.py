from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from . import attorneys, audit, chat, claims, config, crypto, fees
from .admin_api import router as admin_router
from .attorney_api import router as attorney_router
from .auth import create_token, hash_password, verify_password
from .claims import ESTIMATE_DISCLAIMER
from .db import init_db
from .demo import reset_demo_attorney, reset_demo_user
from .deps import Client, CurrentUser, DbSession, encrypt_image
from .legal import deadline_for, legal_basis
from .matching import find_all_matches, find_matches
from .me_api import record_consent, router as me_router, terms_current
from .models import Agreement, Claim, CountySource, IdentityVerification, Notification, PreviousAddress, SurplusRecord, User
from .policies import PRIVACY_VERSION, TERMS_VERSION
from .schemas import (
    AddressOut, AgreementOut, AttorneyPublic, ChatOut, ClaimIn, ClaimOut, CoverageOut, IdentityIn, LoginIn,
    MatchesOut, MatchOut, MatchPreviewOut, MessageIn, PasswordChangeIn, ProfileIn, ProfileOut, SignIn, SignupIn,
    TokenOut,
)
from .security import BodySizeLimit, SecurityHeaders, check_password, login_limiter


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Surpay API", version="0.3.0", lifespan=lifespan)
app.add_middleware(SecurityHeaders)
app.add_middleware(BodySizeLimit)
app.include_router(attorney_router)
app.include_router(me_router)
app.include_router(admin_router)


def _identity_status(user: User) -> str | None:
    return user.identity.review_status if user.identity is not None else None


def _name_locked(user: User) -> bool:
    return _identity_status(user) in ("pending", "approved")


def _profile(user: User) -> ProfileOut:
    ident = user.identity
    session = object_session(user)
    unread = session.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) if session else 0
    return ProfileOut(
        id=user.id, email=user.email, full_name=user.full_name,
        other_names=user.other_names or [], phone=user.phone,
        addresses=[AddressOut(id=a.id, street=a.street, city=a.city, state=a.state, zip=a.zip,
                              county=a.county) for a in user.own_addresses],
        identity_status=_identity_status(user),
        identity_note=ident.review_note if ident is not None and ident.review_status == "rejected" else "",
        name_locked=_name_locked(user),
        role=user.role,
        terms_current=terms_current(user),
        unread_notifications=unread or 0,
        deletion_requested=user.deletion_requested_at is not None,
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


@app.get("/", include_in_schema=False)
def home(session: DbSession):
    """A plain status page for anyone who opens the server's address in a browser."""
    from fastapi.responses import HTMLResponse
    count = session.scalar(select(func.count()).select_from(SurplusRecord).where(SurplusRecord.status == "listed"))
    demo = "on (testing)" if config.DEMO_ENABLED else "off"
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>Surpay API</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:560px;margin:40px auto;padding:0 16px;color:#0f172a}}
.ok{{color:#0b6e4f;font-weight:700}}td{{padding:4px 12px 4px 0}}</style></head><body>
<h1>Surpay API</h1><p class="ok">&#10003; Running (version {app.version})</p>
<table><tr><td>Records tracked</td><td>{count:,}</td></tr><tr><td>Demo login</td><td>{demo}</td></tr></table>
<p>This is the server behind the Surpay app; there is nothing to use here directly.
Staff review: <a href="/admin">/admin</a></p></body></html>""")


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


# --- Accounts -------------------------------------------------------------------------------

@app.post("/auth/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, session: DbSession, client: Client):
    if not body.accept_terms:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Please accept the Terms of Use and Privacy Notice to continue")
    check_password(body.password)
    user = User(email=body.email.lower(), password_hash=hash_password(body.password),
                full_name=body.full_name.strip(), phone=body.phone, other_names=[], role=body.role)
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from None
    record_consent(session, user, "terms", TERMS_VERSION, client)
    record_consent(session, user, "privacy", PRIVACY_VERSION, client)
    audit.record(session, "account.created", actor_id=user.id, entity_type="user", entity_id=user.id,
                 client=client, details={"role": user.role})
    session.commit()
    return TokenOut(token=create_token(user), user=_profile(user))


@app.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, session: DbSession, client: Client):
    email = body.email.lower()
    keys = (f"ip:{client.ip}", f"email:{email}")
    login_limiter.check(*keys)
    user = session.scalar(select(User).where(User.email == email))
    # Check a dummy hash for unknown emails too, so response time doesn't reveal who has an account.
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        login_limiter.fail(*keys)
        audit.record(session, "auth.login_failed", actor_type="anonymous", client=client,
                     details={"email_sha256": crypto.sha256_hex(email)})
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    if user.deletion_requested_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account was closed at your request. Contact support to reopen it.")
    audit.record(session, "auth.login", actor_id=user.id, entity_type="user", entity_id=user.id, client=client)
    session.commit()
    return TokenOut(token=create_token(user), user=_profile(user))


_DUMMY_HASH = hash_password("not-a-real-password-just-for-timing")


@app.post("/auth/change-password", response_model=TokenOut)
def change_password(body: PasswordChangeIn, user: CurrentUser, session: DbSession, client: Client):
    """New password; every other signed-in device is signed out."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your current password isn't right")
    check_password(body.new_password)
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1
    audit.record(session, "auth.password_changed", actor_id=user.id, entity_type="user", entity_id=user.id,
                 client=client)
    session.commit()
    return TokenOut(token=create_token(user), user=_profile(user))


def require_terms(user: User) -> None:
    """The app asks again when the Terms change; the API enforces it too."""
    if not terms_current(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please accept the updated Terms of Use and Privacy Notice")


@app.post("/auth/logout-all")
def logout_everywhere(user: CurrentUser, session: DbSession, client: Client) -> dict:
    """Sign out on every device: all existing tokens stop working."""
    user.token_version = (user.token_version or 0) + 1
    audit.record(session, "auth.logout_all", actor_id=user.id, entity_type="user", entity_id=user.id, client=client)
    session.commit()
    return {"ok": True}


@app.post("/auth/demo", response_model=TokenOut)
def demo_login(session: DbSession, client: Client):
    """One-tap sign-in to a shared, fictional test account. Only when SURPAY_SEED_DEMO=true."""
    if not config.DEMO_ENABLED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo login is turned off on this server")
    user = reset_demo_user(session)
    for kind, version in (("terms", TERMS_VERSION), ("privacy", PRIVACY_VERSION)):
        record_consent(session, user, kind, version, client)
    audit.record(session, "auth.demo_login", actor_id=user.id, entity_type="user", entity_id=user.id, client=client)
    session.commit()
    return TokenOut(token=create_token(user), user=_profile(user))


@app.post("/auth/demo-attorney", response_model=TokenOut)
def demo_attorney_login(session: DbSession, client: Client):
    """One-tap sign-in as a shared, fictional, already-verified attorney with a demo case waiting."""
    if not config.DEMO_ENABLED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo login is turned off on this server")
    user = reset_demo_attorney(session)
    for kind, version in (("terms", TERMS_VERSION), ("privacy", PRIVACY_VERSION)):
        record_consent(session, user, kind, version, client)
    audit.record(session, "auth.demo_login", actor_type="attorney", actor_id=user.id, entity_type="user",
                 entity_id=user.id, client=client)
    session.commit()
    return TokenOut(token=create_token(user), user=_profile(user))


@app.post("/auth/demo-admin")
def demo_admin_login(session: DbSession, client: Client) -> dict:
    """A short-lived pass to the staff dashboard that only sees and acts on demo data (testing only)."""
    from .demo import demo_records
    from .deps import DEMO_ADMIN_HOURS, demo_admin_token
    from .ingest import upsert
    if not config.DEMO_ENABLED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo login is turned off on this server")
    if not session.scalar(select(SurplusRecord.id).where(SurplusRecord.source == "demo",
                                                         SurplusRecord.status == "listed").limit(1)):
        upsert(session, "demo", demo_records(), full_snapshot=True)
    audit.record(session, "auth.demo_admin", actor_type="admin", client=client)
    session.commit()
    return {"token": demo_admin_token(), "expires_in_hours": DEMO_ADMIN_HOURS, "path": "admin"}


@app.get("/me", response_model=ProfileOut)
def get_me(user: CurrentUser):
    return _profile(user)


@app.put("/me", response_model=ProfileOut)
def update_me(body: ProfileIn, user: CurrentUser, session: DbSession, client: Client):
    other_names = [n.strip() for n in body.other_names if n.strip()]
    if _name_locked(user) and (body.full_name.strip() != user.full_name or other_names != (user.other_names or [])):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Your name is locked to your verified ID. Contact support to change it.")
    user.full_name = body.full_name.strip()
    user.other_names = other_names
    user.phone = body.phone
    # Family members' homes are managed with the relative; only the person's own homes change here.
    family = [a for a in user.addresses if a.relative_id is not None]
    user.addresses = [PreviousAddress(**a.model_dump()) for a in body.addresses] + family
    audit.record(session, "profile.updated", actor_id=user.id, entity_type="user", entity_id=user.id,
                 client=client, details={"homes": len(body.addresses)})
    session.commit()
    session.refresh(user)
    return _profile(user)


# --- Results ----------------------------------------------------------------------------------

@app.get("/me/matches/preview", response_model=MatchPreviewOut)
def my_matches_preview(user: CurrentUser, session: DbSession):
    """While ID is under review: only how many possible records, never amounts or details."""
    if user.identity is None or user.identity.review_status == "rejected":
        return MatchPreviewOut(identity_status=_identity_status(user), possible_matches=0)
    return MatchPreviewOut(identity_status=_identity_status(user), possible_matches=len(find_matches(session, user)))


def on_behalf_of(relative) -> str | None:
    if relative is None:
        return None
    label = {"heir": "as heir", "power_of_attorney": "under power of attorney", "guardian": "as guardian"}
    return f"{relative.full_name} (your {relative.relation}, {label.get(relative.basis, relative.basis)})"


@app.get("/me/matches", response_model=MatchesOut)
def my_matches(user: CurrentUser, session: DbSession):
    require_verified(user)
    by_record = {c.record_id: c for c in user.claims}
    out = []
    for m in find_all_matches(session, user):
        r = m.record
        claim = by_record.get(r.id)
        pct = claim.fee_pct if claim is not None and claim.fee_pct is not None else fees.quote(session, r)[0]
        fee = fees.fee_cents(r.amount_cents, pct)
        out.append(MatchOut(
            record_id=r.id, confidence=m.confidence, address_matched=m.address_matched,
            state=r.state, county=r.county, sale_type=r.sale_type, reference=r.reference,
            owner_name=r.owner_name, owner_address=r.owner_address, amount_cents=r.amount_cents,
            fee_pct=pct, estimated_fee_cents=fee, estimated_net_cents=r.amount_cents - fee,
            sale_date=r.sale_date, source_url=r.source_url, last_seen=r.last_seen,
            claim_status=claim.status if claim else None, legal=legal_basis(r.state),
            deadline_date=deadline_for(r.state, r.sale_date),
            relative_id=m.relative.id if m.relative else None, on_behalf_of=on_behalf_of(m.relative),
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


# --- Claims -----------------------------------------------------------------------------------

def claim_out(c: Claim) -> ClaimOut:
    r = c.record
    session = object_session(c)
    pct = fees.for_claim(session, c) if session is not None else (c.fee_pct or config.DEFAULT_FEE_PCT)
    steps = claims.timeline(c)
    ends = [s for s in steps if s["estimate_end"]]
    ident = c.user.identity
    return ClaimOut(
        id=c.id, record_id=r.id, status=c.status, county=r.county, state=r.state,
        reference=r.reference, amount_cents=r.amount_cents,
        estimated_net_cents=r.amount_cents - fees.fee_cents(r.amount_cents, pct),
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
        fee_pct=pct,
        deadline_date=deadline_for(r.state, r.sale_date),
        on_behalf_of=on_behalf_of(c.relative),
        chat_open=chat.thread_open(c),
        unread_messages=sum(1 for m in chat.thread(c) if m.sender_role == "attorney" and m.read_at is None),
        record_listed=r.status == "listed",
    )


def _attorney_public(c: Claim) -> AttorneyPublic | None:
    a = c.attorney.attorney if c.attorney is not None and c.assignment_status == "accepted" else None
    if a is None:
        return None
    return AttorneyPublic(name=a.full_name, firm=a.firm, bar=f"{a.bar_state} Bar #{a.bar_number}")


def _my_claim(user: User, claim_id: int) -> Claim:
    claim = next((c for c in user.claims if c.id == claim_id), None)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    return claim


@app.post("/me/claims", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def start_claim(body: ClaimIn, user: CurrentUser, session: DbSession, client: Client):
    require_verified(user)
    require_terms(user)
    # Only allow claiming records the matcher actually linked to this user (or a verified relative).
    match = next((m for m in find_all_matches(session, user) if m.record.id == body.record_id), None)
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching record for your profile")
    existing = session.scalar(select(Claim).where(Claim.user_id == user.id, Claim.record_id == body.record_id))
    if existing:
        return claim_out(existing)
    claim = claims.new_claim(session, user, body.record_id)
    claim.record = match.record
    claim.relative_id = match.relative.id if match.relative else None
    fees.for_claim(session, claim)
    try:
        session.flush()
    except IntegrityError:  # the same claim started twice at once
        session.rollback()
        return claim_out(session.scalar(select(Claim).where(Claim.user_id == user.id, Claim.record_id == body.record_id)))
    audit.record(session, "claim.started", actor_id=user.id, entity_type="claim", entity_id=claim.id, client=client,
                 details={"record_id": body.record_id, "fee_pct": claim.fee_pct, "relative_id": claim.relative_id})
    session.commit()
    session.refresh(claim)
    return claim_out(claim)


@app.get("/me/claims", response_model=list[ClaimOut])
def my_claims(user: CurrentUser, session: DbSession):
    out = [claim_out(c) for c in sorted(user.claims, key=lambda c: c.created_at, reverse=True)]
    session.commit()  # fees fixed on first view of an older claim
    return out


@app.get("/me/claims/{claim_id}", response_model=ClaimOut)
def my_claim(claim_id: int, user: CurrentUser, session: DbSession):
    out = claim_out(_my_claim(user, claim_id))
    session.commit()
    return out


@app.post("/me/claims/{claim_id}/change-attorney", response_model=ClaimOut)
def change_attorney(claim_id: int, user: CurrentUser, session: DbSession, client: Client):
    """The client's right (agreement section 3) to a different attorney, any time before filing."""
    claim = _my_claim(user, claim_id)
    if claim.attorney_id is None or claim.status not in attorneys.RETURNABLE:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "You can ask for a different attorney once one is assigned and before your claim is filed")
    old = claim.attorney_id
    session.add(Notification(user_id=old, kind="claim_update", title="A client asked for a different attorney",
                             body=f"Case #{claim.id} has been reassigned at the client's request.", claim_id=claim.id))
    attorneys.decline(session, claim, old, reason="You asked for a different attorney. We're finding you another one.")
    audit.record(session, "claim.attorney_change_requested", actor_id=user.id, entity_type="claim",
                 entity_id=claim.id, client=client, details={"previous_attorney": old})
    session.commit()
    return claim_out(claim)


@app.post("/me/identity", response_model=list[ClaimOut])
def submit_identity(body: IdentityIn, user: CurrentUser, session: DbSession, client: Client):
    """Submit ID for review. Shared by all of the user's claims; resubmit after a rejection."""
    require_terms(user)
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
    session.flush()
    record_consent(session, user, "identity_processing", PRIVACY_VERSION, client)
    audit.record(session, "identity.submitted", actor_id=user.id, entity_type="identity",
                 entity_id=user.identity.id, client=client,
                 details={"legal_name": body.legal_name.strip(), "id_type": body.id_type,
                          "id_front_sha256": crypto.sha256_hex(body.id_front_b64),
                          "selfie_sha256": crypto.sha256_hex(body.selfie_b64)})
    session.commit()
    session.refresh(user)
    return [claim_out(c) for c in user.claims]


@app.get("/me/identity/status", response_model=ProfileOut)
def identity_status(user: CurrentUser):
    """Same as GET /me; the app polls this while waiting for review."""
    return _profile(user)


# --- Agreement --------------------------------------------------------------------------------

def legal_name(user: User) -> str:
    return user.identity.legal_name if user.identity is not None else user.full_name


@app.get("/me/claims/{claim_id}/agreement", response_model=AgreementOut)
def get_agreement(claim_id: int, user: CurrentUser, session: DbSession):
    claim = _my_claim(user, claim_id)
    a = claim.agreement
    if a:
        return AgreementOut(version=a.version, text=a.text, fee_pct=a.fee_pct, signed=True,
                            signature_name=a.signature_name, signed_at=a.signed_at,
                            expected_name=a.legal_name_on_id or a.signature_name, document_sha256=a.document_sha256)
    pct = fees.for_claim(session, claim)
    session.commit()
    text = claims.agreement_text(claim, user, pct)
    return AgreementOut(version=claims.AGREEMENT_VERSION, text=text, fee_pct=pct, signed=False,
                        signature_name=None, signed_at=None, expected_name=legal_name(user),
                        document_sha256=crypto.sha256_hex(text))


def _signature_png(b64: str) -> bytes:
    import base64
    import binascii
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please draw your signature") from None
    if not data.startswith(b"\x89PNG") or len(data) > 2 * 1024 * 1024:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please draw your signature")
    return data


@app.post("/me/claims/{claim_id}/agreement", response_model=ClaimOut)
def sign_agreement(claim_id: int, body: SignIn, user: CurrentUser, session: DbSession, client: Client):
    claim = _my_claim(user, claim_id)
    require_terms(user)
    if claim.agreement is not None:
        return claim_out(claim)
    if claim.status != "identity_submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Verify your identity before signing")
    if not body.agreed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please tick the box to agree")
    legal = legal_name(user)
    if not claims.names_match(body.signature_name, legal):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Type your full legal name exactly as it appears on your ID: {legal}")
    png = _signature_png(body.signature_png_b64)
    pct = fees.for_claim(session, claim)
    text = claims.agreement_text(claim, user, pct)
    digest = crypto.sha256_hex(text)
    claim.agreement = Agreement(
        version=claims.AGREEMENT_VERSION, text=text, fee_pct=pct, signature_name=body.signature_name.strip(),
        ip_address=client.ip, user_agent=client.user_agent[:255], signature_image=crypto.encrypt(png),
        document_sha256=digest, device_id=client.device_id[:128], device_info=client.device_info[:255],
        legal_name_on_id=legal, signed_at=datetime.now(timezone.utc),
    )
    claims.advance(claim, "agreement_signed")
    claims.sync_with_identity(claim, user)
    session.flush()
    record_consent(session, user, "agreement", f"{claims.AGREEMENT_VERSION}:{claim.id}", client)
    audit.record(session, "agreement.signed", actor_id=user.id, entity_type="claim", entity_id=claim.id,
                 client=client, details={"document_sha256": digest, "signature_sha256": crypto.sha256_hex(png),
                                         "typed_name": body.signature_name.strip(), "legal_name": legal,
                                         "fee_pct": pct, "version": claims.AGREEMENT_VERSION})
    try:
        session.commit()
    except IntegrityError:  # signed twice at once: the first one counts
        session.rollback()
        return claim_out(_my_claim(user, claim_id))
    attorneys.assign_ready(session)
    session.refresh(claim)
    return claim_out(claim)


# --- Messages with the attorney ------------------------------------------------------------------

def chat_out(claim: Claim, viewer_role: str) -> ChatOut:
    has_attorney_msg = any(m.sender_role == "attorney" for m in chat.thread(claim))
    open_ = chat.thread_open(claim)
    if viewer_role == "claimant":
        can_send = open_ and has_attorney_msg
        waiting = "" if can_send else (
            "Your attorney will send the first message once they've reviewed your case."
            if open_ else "Messages open once an attorney accepts your case.")
        a = claim.attorney.attorney if claim.attorney is not None else None
        counterpart = ", ".join(x for x in (a.full_name, a.firm) if x) if a and open_ else "Your attorney"
    else:
        can_send, waiting = open_, ""
        rel = claim.relative
        counterpart = legal_name(claim.user) + (f" (for {rel.full_name})" if rel else "")
    return ChatOut(messages=[chat.message_out(m) for m in chat.thread(claim)], can_send=can_send,
                   waiting_reason=waiting, counterpart=counterpart, code_of_conduct=chat.CODE_OF_CONDUCT)


@app.get("/me/claims/{claim_id}/messages", response_model=ChatOut)
def my_messages(claim_id: int, user: CurrentUser, session: DbSession):
    claim = _my_claim(user, claim_id)
    chat.mark_read(claim, "claimant")
    session.commit()
    return chat_out(claim, "claimant")


@app.post("/me/claims/{claim_id}/messages", response_model=ChatOut)
def send_my_message(claim_id: int, body: MessageIn, user: CurrentUser, session: DbSession, client: Client):
    claim = _my_claim(user, claim_id)
    require_terms(user)
    msg = chat.send(session, claim, user, "claimant", body.body)
    session.flush()
    audit.record(session, "message.sent", actor_id=user.id, entity_type="message", entity_id=msg.id, client=client,
                 details={"claim_id": claim.id, "body_sha256": crypto.sha256_hex(msg.body)})
    session.commit()
    return chat_out(claim, "claimant")


# --- Reference data -------------------------------------------------------------------------------

@app.get("/counties")
def counties_in_state(state: str, session: DbSession) -> list[str]:
    """County names for one state, for the address form (e.g. ["Adams County", ...])."""
    names = list(session.scalars(
        select(CountySource.county).where(CountySource.state == state.upper()).order_by(CountySource.county)
    ))
    if config.DEMO_ENABLED and state.upper() == "OH":
        names.insert(0, "Demo County")  # so a test attorney can take the fictional demo cases
    return names
