from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config
from .auth import create_token, current_user, hash_password, verify_password
from .db import get_session, init_db
from .demo import reset_demo_user
from .matching import find_matches
from .models import Claim, PreviousAddress, SurplusRecord, User
from .schemas import (
    AddressOut, ClaimIn, ClaimOut, CoverageOut, LoginIn, MatchesOut, MatchOut, ProfileIn,
    ProfileOut, SignupIn, TokenOut,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Surpay API", version="0.1.0", lifespan=lifespan)

DbSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


def _profile(user: User) -> ProfileOut:
    return ProfileOut(
        id=user.id, email=user.email, full_name=user.full_name,
        other_names=user.other_names or [], phone=user.phone,
        addresses=[AddressOut(id=a.id, street=a.street, city=a.city, state=a.state, zip=a.zip)
                   for a in user.addresses],
    )


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
                full_name=body.full_name.strip(), phone=body.phone, other_names=[])
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
    user.full_name = body.full_name.strip()
    user.other_names = [n.strip() for n in body.other_names if n.strip()]
    user.phone = body.phone
    user.addresses = [PreviousAddress(**a.model_dump()) for a in body.addresses]
    session.add(user)
    session.commit()
    session.refresh(user)
    return _profile(user)


@app.get("/me/matches", response_model=MatchesOut)
def my_matches(user: CurrentUser, session: DbSession):
    claims = {c.record_id: c.status for c in user.claims}
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
            claim_status=claims.get(r.id),
        ))
    searched = session.scalar(select(func.count()).select_from(SurplusRecord)
                              .where(SurplusRecord.status == "listed"))
    return MatchesOut(
        matches=out,
        total_amount_cents=sum(m.amount_cents for m in out),
        total_estimated_net_cents=sum(m.estimated_net_cents for m in out),
        records_searched=searched,
        counties_covered=_covered_counties(session),
    )


def _claim_out(c: Claim) -> ClaimOut:
    r = c.record
    return ClaimOut(id=c.id, record_id=r.id, status=c.status, county=r.county, state=r.state,
                    reference=r.reference, amount_cents=r.amount_cents,
                    created_at=c.created_at, updated_at=c.updated_at)


@app.post("/me/claims", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def start_claim(body: ClaimIn, user: CurrentUser, session: DbSession):
    # Only allow claiming records the matcher actually linked to this user.
    if body.record_id not in {m.record.id for m in find_matches(session, user)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching record for your profile")
    existing = session.scalar(select(Claim).where(Claim.user_id == user.id, Claim.record_id == body.record_id))
    if existing:
        return _claim_out(existing)
    claim = Claim(user_id=user.id, record_id=body.record_id)
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return _claim_out(claim)


@app.get("/me/claims", response_model=list[ClaimOut])
def my_claims(user: CurrentUser):
    return [_claim_out(c) for c in sorted(user.claims, key=lambda c: c.created_at, reverse=True)]
