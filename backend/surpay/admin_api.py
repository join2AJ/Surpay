"""Staff review (enabled by SURPAY_ADMIN_TOKEN): identities, family claims, claims, attorneys,
fee rules, the audit trail and signing evidence."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from . import attorneys, audit, chat, claims, config, crypto, fees
from .audit import ClientInfo
from .demo import is_demo_attorney, is_demo_claim, is_demo_user
from .deps import Admin, AdminScope, Client, DbSession
from .matching import find_matches, find_relative_matches
from .models import (
    AttorneyProfile, AuditLog, Claim, ClaimEvent, FeeBand, FeeRule, IdentityVerification, Relative, User,
)
from .schemas import (
    AddressOut, AdminAttorneyIn, AdminFeeBandsIn, AdminFeeOverrideIn, AdminFeeRuleIn, AdminIdentityIn, AdminStatusIn,
)

router = APIRouter(tags=["admin"], include_in_schema=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(session, action: str, client: ClientInfo, entity_type: str = "", entity_id: int | None = None,
         **details) -> None:
    audit.record(session, action, actor_type="admin", client=client, entity_type=entity_type,
                 entity_id=entity_id, details=details)


def _image(blob: bytes | None) -> Response:
    if blob is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not provided")
    data = crypto.decrypt(blob)
    media = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return Response(data, media_type=media, headers={"Cache-Control": "no-store"})


def _addresses(user: User, relative_id: int | None = None) -> list[dict]:
    return [AddressOut(id=a.id, street=a.street, city=a.city, state=a.state, zip=a.zip, county=a.county).model_dump()
            for a in user.addresses if a.relative_id == relative_id]


def _identity(i: IdentityVerification | None) -> dict | None:
    if i is None:
        return None
    return {"legal_name": i.legal_name, "date_of_birth": i.date_of_birth.isoformat(), "ssn_last4": i.ssn_last4,
            "phone": i.phone, "address": f"{i.street}, {i.city}, {i.state} {i.zip}", "id_type": i.id_type,
            "has_id_back": i.id_back is not None, "review_status": i.review_status,
            "review_note": i.review_note, "submitted_at": i.submitted_at.isoformat()}


@router.get("/admin", response_class=HTMLResponse)
def admin_page():
    if not config.ADMIN_TOKEN and not config.DEMO_ENABLED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return HTMLResponse((Path(__file__).parent / "static" / "admin.html").read_text(), headers={
        "Content-Security-Policy": "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
                                   "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"})


@router.get("/admin/whoami")
def admin_whoami(scope: Admin) -> dict:
    return {"demo": scope.demo}


# --- Claims -------------------------------------------------------------------------------------

def admin_claim(c: Claim, scope: AdminScope | None = None) -> dict:
    out = _admin_claim(c)
    if scope is not None and scope.demo and not is_demo_user(c.user):
        # A real person testing with the demo record: the demo admin never sees their details.
        out["user"] = {"id": c.user.id, "email": "(a tester: hidden in the admin demo)", "full_name": "Tester",
                       "phone": "", "addresses": []}
        out["identity"] = None
        if out.get("agreement"):
            out["agreement"] = {**out["agreement"], "ip_address": "hidden", "device": "hidden", "device_id": "hidden",
                                "has_signature_image": False}
    return out


def _admin_claim(c: Claim) -> dict:
    from .api import claim_out
    from .attorney_api import other_claimants
    u = c.user
    a = c.agreement
    return {
        **claim_out(c).model_dump(mode="json"),
        "user": {"id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone,
                 "addresses": _addresses(u, c.relative_id)},
        "owner_name": c.record.owner_name, "owner_address": c.record.owner_address,
        "identity": _identity(u.identity),
        "relative": None if c.relative is None else {"id": c.relative.id, "name": c.relative.full_name,
                                                     "relationship": c.relative.relation,
                                                     "basis": c.relative.basis,
                                                     "review_status": c.relative.review_status},
        "fee_basis": c.fee_basis or {},
        "attorney": None if c.attorney is None or c.attorney.attorney is None else {
            "name": c.attorney.attorney.full_name, "firm": c.attorney.attorney.firm,
            "assignment_status": c.assignment_status, "fee_cents": c.attorney_fee_cents,
            "payout_status": c.payout_status,
        },
        "agreement": None if a is None else {
            "signature_name": a.signature_name, "legal_name_on_id": a.legal_name_on_id,
            "signed_at": a.signed_at.isoformat(), "version": a.version, "ip_address": a.ip_address,
            "device": a.device_info, "device_id": a.device_id, "document_sha256": a.document_sha256,
            "has_signature_image": a.signature_image is not None,
        },
        "messages": len(c.messages),
        "other_claimants": other_claimants(c),
        "record_listed": c.record.status == "listed",
        "history": [{"status": e.status, "note": e.note, "at": e.created_at.isoformat()} for e in c.events],
    }


def _claim(session, claim_id: int, scope: AdminScope, personal: bool = False) -> Claim:
    """The claim, if this dashboard user may see it (personal: also the claimant's own documents)."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    scope.check(is_demo_claim(claim) and (not personal or is_demo_user(claim.user)))
    return claim


@router.get("/admin/claims")
def admin_claims(scope: Admin, session: DbSession) -> list[dict]:
    out = [admin_claim(c, scope) for c in session.scalars(select(Claim).order_by(Claim.id.desc()))
           if not scope.demo or is_demo_claim(c)]
    session.commit()
    return out


@router.post("/admin/claims/{claim_id}/status")
def admin_set_status(claim_id: int, body: AdminStatusIn, scope: Admin, session: DbSession, client: Client) -> dict:
    claim = _claim(session, claim_id, scope)
    try:
        claims.set_status(claim, body.status, body.note)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    attorneys.settle_payout(claim)
    if body.status == "withdrawn":
        attorneys.release(session, claim)  # an offered case leaves the attorney's list
    _log(session, "admin.claim_status", client, "claim", claim.id, status=body.status, note=body.note)
    session.commit()
    attorneys.assign_ready(session)
    return admin_claim(claim, scope)


@router.post("/admin/claims/{claim_id}/reassign")
def admin_reassign(claim_id: int, scope: Admin, session: DbSession, client: Client) -> dict:
    """Take the case away from its current attorney (e.g. no response) and offer it to the next."""
    claim = _claim(session, claim_id, scope)
    if claim.attorney_id:
        attorneys.decline(session, claim, claim.attorney_id)
    else:
        attorneys.offer(session, claim)
    _log(session, "admin.claim_reassigned", client, "claim", claim.id)
    session.commit()
    return admin_claim(claim, scope)


@router.post("/admin/claims/{claim_id}/payout")
def admin_payout(claim_id: int, scope: Admin, session: DbSession, client: Client) -> dict:
    """Record that the attorney's per-case fee has been paid."""
    claim = _claim(session, claim_id, scope)
    if claim.payout_status != "due":
        raise HTTPException(status.HTTP_409_CONFLICT, "No payout due on this claim")
    claim.payout_status = "paid"
    claim.events.append(ClaimEvent(status=claim.status, note="Attorney fee paid", created_at=_now()))
    _log(session, "admin.attorney_paid", client, "claim", claim.id, cents=claim.attorney_fee_cents)
    session.commit()
    return admin_claim(claim, scope)


@router.post("/admin/claims/{claim_id}/fee")
def admin_fee_override(claim_id: int, body: AdminFeeOverrideIn, scope: Admin, session: DbSession, client: Client) -> dict:
    """Set this case's fee by hand. Only before the client signs; the signed fee never changes."""
    claim = _claim(session, claim_id, scope)
    if claim.agreement is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The client has already signed at the current fee")
    _, basis = fees.quote(session, claim.record)
    cap = basis.get("legal_max_pct")
    if cap is not None and body.fee_pct > cap:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Above the legal maximum of {cap:g}% here")
    claim.fee_pct = body.fee_pct
    claim.fee_basis = {**basis, "final_pct": body.fee_pct, "override": True, "override_note": body.note}
    _log(session, "admin.fee_override", client, "claim", claim.id, fee_pct=body.fee_pct, note=body.note)
    session.commit()
    return admin_claim(claim, scope)


@router.get("/admin/claims/{claim_id}/messages")
def admin_messages(claim_id: int, scope: Admin, session: DbSession, client: Client) -> list[dict]:
    """For disputes and misuse reports only; every view is logged."""
    claim = _claim(session, claim_id, scope, personal=True)
    _log(session, "admin.messages_viewed", client, "claim", claim.id)
    session.commit()
    return [{**chat.message_out(m), "created_at": m.created_at.isoformat()} for m in claim.messages]


@router.get("/admin/claims/{claim_id}/signature")
def admin_signature(claim_id: int, scope: Admin, session: DbSession):
    claim = _claim(session, claim_id, scope, personal=True)
    return _image(claim.agreement.signature_image if claim.agreement else None)


@router.get("/admin/claims/{claim_id}/evidence")
def admin_evidence(claim_id: int, scope: Admin, session: DbSession) -> dict:
    """Certificate of signing: who signed what, when, from which device, and the proof trail."""
    claim = _claim(session, claim_id, scope, personal=True)
    a, u = claim.agreement, claim.user
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not signed")
    trail = session.scalars(select(AuditLog).where(AuditLog.actor_id == u.id).order_by(AuditLog.id)).all()
    return {
        "claim_id": claim.id, "agreement_version": a.version,
        "document_sha256": a.document_sha256, "text_unchanged": crypto.sha256_hex(a.text) == a.document_sha256,
        "typed_name": a.signature_name, "legal_name_on_id": a.legal_name_on_id,
        "name_matches_id": claims.names_match(a.signature_name, a.legal_name_on_id or ""),
        "signed_at": a.signed_at.isoformat(), "ip_address": a.ip_address, "user_agent": a.user_agent,
        "device_id": a.device_id, "device": a.device_info,
        "identity": _identity(u.identity),
        "audit_chain": audit.verify(session),
        "trail": [audit.entry_out(e) for e in trail],
    }


# --- Identities -------------------------------------------------------------------------------------

@router.get("/admin/identities")
def admin_identities(scope: Admin, session: DbSession, review_status: str = "pending") -> list[dict]:
    """People waiting for ID review (or approved / rejected), oldest first, with what they listed."""
    rows = session.scalars(
        select(IdentityVerification).where(IdentityVerification.review_status == review_status)
        .order_by(IdentityVerification.submitted_at)
    )
    everyone = session.scalars(select(IdentityVerification)).all()

    def duplicates(i: IdentityVerification) -> list[str]:
        """Other accounts with the same person's details: a second account, or someone using their ID."""
        same = []
        for o in everyone:
            if o.id == i.id or o.date_of_birth != i.date_of_birth:
                continue
            if o.ssn_last4 == i.ssn_last4 or claims.names_match(o.legal_name, i.legal_name):
                same.append(o.user.email)
        return same

    rows = [i for i in rows if not scope.demo or is_demo_user(i.user)]
    return [{
        "user": {"id": i.user.id, "email": i.user.email, "full_name": i.user.full_name,
                 "other_names": i.user.other_names or [], "addresses": _addresses(i.user)},
        "identity": _identity(i),
        "possible_matches": len(find_matches(session, i.user)),
        "possible_duplicates": duplicates(i),
    } for i in rows]


@router.get("/admin/users/{user_id}/documents/{kind}")
def admin_document(user_id: int, kind: str, scope: Admin, session: DbSession):
    user = session.get(User, user_id)
    if user is None or user.identity is None or kind not in ("id_front", "id_back", "selfie"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    scope.check(is_demo_user(user))
    return _image(getattr(user.identity, kind))


@router.post("/admin/users/{user_id}/identity")
def admin_review_identity(user_id: int, body: AdminIdentityIn, scope: Admin, session: DbSession, client: Client) -> dict:
    user = session.get(User, user_id)
    if user is None or user.identity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No identity submitted")
    scope.check(is_demo_user(user))  # approving a real person's ID would unlock real records
    user.identity.review_status = body.decision
    user.identity.review_note = body.note
    user.identity.reviewed_at = _now()
    if body.decision == "approved":
        user.full_name = user.identity.legal_name  # searches use the verified name from now on
    reset = 0
    for c in user.claims:
        if body.decision == "approved":
            claims.sync_with_identity(c, user)
        elif c.status in ("identity_submitted", "agreement_signed"):
            # Send them back to re-upload; a signed agreement stays on file.
            claims.set_status(c, "requested", f"ID needs to be resubmitted: {body.note}")
            reset += 1
    from .models import Notification
    # Claims that moved already sent their own notification; don't send the same news twice.
    already = (any(c.status == "identity_verified" for c in user.claims) if body.decision == "approved" else reset > 0)
    if not already:
        session.add(Notification(
            user_id=user.id, kind="identity",
            title="Your identity is verified" if body.decision == "approved" else "Please resubmit your ID",
            body="Your results are ready to view." if body.decision == "approved" else (body.note or "Open the app.")))
    _log(session, f"admin.identity_{body.decision}", client, "user", user.id, note=body.note)
    session.commit()
    attorneys.assign_ready(session)
    return {"ok": True}


# --- Family members (heir claims) ---------------------------------------------------------------------

@router.get("/admin/relatives")
def admin_relatives(scope: Admin, session: DbSession, review_status: str = "pending") -> list[dict]:
    rows = [r for r in session.scalars(select(Relative).where(Relative.review_status == review_status)
                                       .order_by(Relative.submitted_at)) if not scope.demo or is_demo_user(r.user)]
    return [{
        "id": r.id, "user": {"id": r.user.id, "email": r.user.email,
                             "verified_name": r.user.identity.legal_name if r.user.identity else r.user.full_name,
                             "identity_status": r.user.identity.review_status if r.user.identity else None},
        "full_name": r.full_name, "other_names": r.other_names or [], "relationship": r.relation,
        "basis": r.basis, "date_of_death": r.date_of_death.isoformat() if r.date_of_death else None,
        "documents": [k for k in ("relationship_proof", "death_certificate", "authority_document") if getattr(r, k)],
        "addresses": _addresses(r.user, r.id), "review_status": r.review_status, "review_note": r.review_note,
        "submitted_at": r.submitted_at.isoformat(),
        "possible_matches": len(find_relative_matches(session, r.user, r)),
    } for r in rows]


@router.get("/admin/relatives/{relative_id}/documents/{kind}")
def admin_relative_document(relative_id: int, kind: str, scope: Admin, session: DbSession):
    r = session.get(Relative, relative_id)
    if r is None or kind not in ("relationship_proof", "death_certificate", "authority_document"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    scope.check(is_demo_user(r.user))
    return _image(getattr(r, kind))


@router.post("/admin/relatives/{relative_id}")
def admin_review_relative(relative_id: int, body: AdminIdentityIn, scope: Admin, session: DbSession,
                          client: Client) -> dict:
    r = session.get(Relative, relative_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    scope.check(is_demo_user(r.user))
    r.review_status, r.review_note, r.reviewed_at = body.decision, body.note, _now()
    from .models import Notification
    session.add(Notification(
        user_id=r.user_id, kind="relative",
        title=f"Search for {r.full_name} " + ("approved" if body.decision == "approved" else "needs more documents"),
        body="Any records found are now in My money." if body.decision == "approved" else (body.note or "")))
    _log(session, f"admin.relative_{body.decision}", client, "relative", r.id, note=body.note)
    session.commit()
    return {"ok": True}


# --- Attorneys --------------------------------------------------------------------------------------

@router.get("/admin/attorneys")
def admin_attorneys(scope: Admin, session: DbSession, review_status: str = "pending") -> list[dict]:
    rows = session.scalars(select(AttorneyProfile).where(AttorneyProfile.status == review_status)
                           .order_by(AttorneyProfile.created_at))
    out = []
    for a in rows:
        if scope.demo and not is_demo_attorney(a):
            continue
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


@router.get("/admin/attorneys/{user_id}/bar-card")
def admin_bar_card(user_id: int, scope: Admin, session: DbSession):
    user = session.get(User, user_id)
    if user is None or user.attorney is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    scope.check(is_demo_attorney(user.attorney))
    return _image(user.attorney.bar_card)


@router.post("/admin/attorneys/{user_id}")
def admin_review_attorney(user_id: int, body: AdminAttorneyIn, scope: Admin, session: DbSession, client: Client) -> dict:
    user = session.get(User, user_id)
    if user is None or user.attorney is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No application")
    scope.check(is_demo_attorney(user.attorney))  # only Demo County attorneys: they can only get demo cases
    user.attorney.status = body.decision
    user.attorney.review_note = body.note
    user.attorney.reviewed_at = _now()
    if body.decision == "rejected":
        # A suspended attorney's open cases go to someone else rather than waiting forever.
        for c in session.scalars(select(Claim).where(Claim.attorney_id == user_id,
                                                     Claim.assignment_status.in_(("offered", "accepted")))):
            if not attorneys.is_closed(c):
                attorneys.decline(session, c, user_id,
                                  reason="Your attorney is no longer available. We're finding you another one.")
    _log(session, f"admin.attorney_{body.decision}", client, "attorney", user.attorney.id, note=body.note)
    session.commit()
    offered = attorneys.assign_ready(session)  # cases waiting in their counties go out now
    return {"ok": True, "cases_offered": offered}


# --- Fees ---------------------------------------------------------------------------------------------

def _rule_out(r: FeeRule) -> dict:
    return {"id": r.id, "state": r.state, "county": r.county, "base_pct": r.base_pct,
            "legal_max_pct": r.legal_max_pct, "legal_source": r.legal_source, "note": r.note,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


@router.get("/admin/fees")
def admin_fees(scope: Admin, session: DbSession) -> dict:
    rules = session.scalars(select(FeeRule).order_by(FeeRule.state, FeeRule.county)).all()
    bands = sorted(session.scalars(select(FeeBand)).all(),
                   key=lambda b: (b.up_to_cents is None, b.up_to_cents or 0))
    return {"default_pct": config.DEFAULT_FEE_PCT, "rules": [_rule_out(r) for r in rules],
            "bands": [{"up_to_cents": b.up_to_cents, "pct": b.pct} for b in bands],
            "formula": "fee = average(county rate, amount band rate), capped at the legal maximum, "
                       "rounded to 0.5%"}


@router.post("/admin/fees/rules")
def admin_save_rule(body: AdminFeeRuleIn, scope: Admin, session: DbSession, client: Client) -> dict:
    scope.read_only()
    county = body.county.strip()
    rule = session.scalar(select(FeeRule).where(FeeRule.state == body.state, FeeRule.county == county))
    if rule is None:
        rule = FeeRule(state=body.state, county=county)
        session.add(rule)
    rule.base_pct, rule.legal_max_pct = body.base_pct, body.legal_max_pct
    rule.legal_source, rule.note, rule.updated_at = body.legal_source, body.note, _now()
    session.flush()
    _log(session, "admin.fee_rule_saved", client, "fee_rule", rule.id, **body.model_dump())
    session.commit()
    return _rule_out(rule)


@router.delete("/admin/fees/rules/{rule_id}")
def admin_delete_rule(rule_id: int, scope: Admin, session: DbSession, client: Client) -> dict:
    scope.read_only()
    rule = session.get(FeeRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    session.delete(rule)
    _log(session, "admin.fee_rule_deleted", client, "fee_rule", rule_id)
    session.commit()
    return {"ok": True}


@router.put("/admin/fees/bands")
def admin_save_bands(body: AdminFeeBandsIn, scope: Admin, session: DbSession, client: Client) -> dict:
    scope.read_only()
    try:
        bands = [(int(b["up_to_cents"]) if b.get("up_to_cents") is not None else None, float(b["pct"]))
                 for b in body.bands]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Each band needs up_to_cents and pct") from None
    if sum(1 for up, _ in bands if up is None) != 1 or any(not 0 <= p <= 50 for _, p in bands):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Exactly one open-ended band, and every rate between 0 and 50%")
    for b in session.scalars(select(FeeBand)):
        session.delete(b)
    session.add_all(FeeBand(up_to_cents=up, pct=p) for up, p in bands)
    _log(session, "admin.fee_bands_saved", client, bands=body.bands)
    session.commit()
    return admin_fees(scope, session)


@router.get("/admin/fees/quote")
def admin_fee_quote(record_id: int, scope: Admin, session: DbSession) -> dict:
    from .models import SurplusRecord
    r = session.get(SurplusRecord, record_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    pct, basis = fees.quote(session, r)
    return {"record_id": r.id, "county": r.county, "state": r.state, "amount_cents": r.amount_cents, **basis}


# --- Audit trail and account closures --------------------------------------------------------------------

@router.get("/admin/audit")
def admin_audit(scope: Admin, session: DbSession, user_id: int | None = None, claim_id: int | None = None,
                limit: int = 200) -> list[dict]:
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 1000))
    if scope.demo:  # only the fictional accounts' activity
        demo_ids = list(session.scalars(select(User.id).where(User.email.like("%@surpay.test"))))
        q = q.where(AuditLog.actor_id.in_(demo_ids))
    if user_id is not None:
        q = q.where(AuditLog.actor_id == user_id)
    if claim_id is not None:
        q = q.where(AuditLog.entity_type == "claim", AuditLog.entity_id == claim_id)
    return [audit.entry_out(e) for e in session.scalars(q)]


@router.get("/admin/audit/verify")
def admin_audit_verify(scope: Admin, session: DbSession) -> dict:
    return audit.verify(session)


@router.get("/admin/deletion-requests")
def admin_deletion_requests(scope: Admin, session: DbSession) -> list[dict]:
    if scope.demo:
        return []
    rows = session.scalars(select(User).where(User.deletion_requested_at.is_not(None)))
    return [{"user_id": u.id, "email": u.email, "requested_at": u.deletion_requested_at.isoformat(),
             "claims": [{"id": c.id, "status": c.status} for c in u.claims]} for u in rows]
