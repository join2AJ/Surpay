"""Staff review (enabled by SURPAY_ADMIN_TOKEN): identities, family claims, claims, attorneys,
fee rules, the audit trail and signing evidence."""

from datetime import datetime, timedelta, timezone
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


# --- Overview: how much we track, how the pipeline is doing, what needs attention -------------------------

def _aware(dt: datetime | None) -> datetime | None:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


@router.get("/admin/overview")
def admin_overview(scope: Admin, session: DbSession) -> dict:
    """Headline numbers for the dashboard. County lists are public, so record totals are shown in the demo too;
    people and claims are counted for the demo data only."""
    from collections import Counter

    from . import counties
    from .models import ScrapeRun, SurplusRecord
    from .scrapers import SOURCES

    now = _now()
    listed = select(SurplusRecord).where(SurplusRecord.status == "listed")
    records = session.scalars(listed).all()
    by_county: dict[tuple[str, str], list[int]] = {}
    for r in records:
        by_county.setdefault((r.state, r.county), []).append(r.amount_cents)
    counties_rows = sorted(
        [{"state": s, "county": c, "records": len(v), "total_cents": sum(v), "largest_cents": max(v)}
         for (s, c), v in by_county.items()], key=lambda x: -x["total_cents"])
    bands = Counter("under $5k" if r.amount_cents < 500_000 else "$5k-$25k" if r.amount_cents < 2_500_000
                    else "$25k-$100k" if r.amount_cents < 10_000_000 else "$100k+" for r in records)
    delisted = session.scalar(select(func.count()).select_from(SurplusRecord).where(SurplusRecord.status != "listed"))
    new_7d = sum(1 for r in records if _aware(r.first_seen) and _aware(r.first_seen) > now - timedelta(days=7))

    sources = []
    for name, cls in SOURCES.items():
        last = session.scalars(select(ScrapeRun).where(ScrapeRun.source == name).order_by(ScrapeRun.id.desc()).limit(1)).first()
        last_ok = session.scalars(select(ScrapeRun).where(ScrapeRun.source == name, ScrapeRun.ok.is_(True))
                                  .order_by(ScrapeRun.id.desc()).limit(1)).first()
        n = session.scalar(select(func.count()).select_from(SurplusRecord).where(
            SurplusRecord.source == name, SurplusRecord.status == "listed"))
        age_h = (now - _aware(last_ok.finished_at or last_ok.started_at)).total_seconds() / 3600 if last_ok else None
        sources.append({"source": name, "description": cls.description, "records": n,
                        "last_run": _aware(last.started_at).isoformat() if last else None,
                        "last_ok": bool(last and last.ok), "last_error": (last.error if last and not last.ok else "")[:300],
                        "hours_since_success": round(age_h, 1) if age_h is not None else None,
                        "healthy": age_h is not None and age_h < 48 and bool(last and last.ok)})

    claims_q = session.scalars(select(Claim)).all()
    if scope.demo:
        claims_q = [c for c in claims_q if is_demo_claim(c)]
    funnel = Counter(c.status for c in claims_q)
    active = [c for c in claims_q if c.status not in ("paid", "denied", "withdrawn")]
    pipeline_fees = sum(fees.fee_cents(c.record.amount_cents, c.fee_pct or 0) for c in active)
    recovered = sum(c.record.amount_cents for c in claims_q if c.status == "paid")
    payouts_due = sum(c.attorney_fee_cents for c in claims_q if c.payout_status == "due")

    users = session.scalars(select(User)).all()
    if scope.demo:
        users = [u for u in users if is_demo_user(u) or (u.attorney is not None and is_demo_attorney(u.attorney))]
    ids = [u.identity for u in users if u.identity is not None]
    lawyers = [u.attorney for u in users if u.attorney is not None]

    alerts = []
    stale_ids = [i for i in ids if i.review_status == "pending" and _aware(i.submitted_at) < now - timedelta(days=1)]
    if stale_ids:
        alerts.append(f"{len(stale_ids)} ID review(s) waiting more than 1 day")
    stale_offers = [c for c in claims_q if c.assignment_status == "offered" and _aware(c.assigned_at)
                    and _aware(c.assigned_at) < now - timedelta(days=2)]
    if stale_offers:
        alerts.append(f"{len(stale_offers)} case offer(s) unanswered for more than 2 days")
    unassigned = [c for c in claims_q if c.status == "identity_verified" and not c.attorney_id]
    if unassigned:
        alerts.append(f"{len(unassigned)} verified claim(s) with no attorney serving the county")
    silent = [c for c in claims_q if c.assignment_status == "accepted" and _aware(c.accepted_at)
              and _aware(c.accepted_at) < now - timedelta(days=3) and not any(m.sender_role == "attorney" for m in chat.thread(c))
              and c.status not in ("paid", "denied", "withdrawn")]
    if silent:
        alerts.append(f"{len(silent)} accepted case(s) where the attorney hasn't messaged the client in 3 days")
    unhealthy = [s["source"] for s in sources if not s["healthy"] and s["source"] != "demo"]
    if unhealthy:
        alerts.append(f"Scraper needs attention: {', '.join(unhealthy)}")
    if payouts_due:
        alerts.append(f"Attorney payouts due: ${payouts_due / 100:,.2f}")

    return {
        "demo": scope.demo,
        "records": {"listed": len(records), "total_cents": sum(r.amount_cents for r in records),
                    "counties": len(by_county), "delisted": delisted, "new_last_7_days": new_7d,
                    "by_size": dict(bands), "by_county": counties_rows},
        "registry": {k: dict(v) if hasattr(v, "items") else v for k, v in counties.summary(session).items()},
        "sources": sources,
        "people": {"accounts": len(users), "claimants": sum(1 for u in users if u.role == "claimant"),
                   "ids_pending": sum(1 for i in ids if i.review_status == "pending"),
                   "ids_approved": sum(1 for i in ids if i.review_status == "approved"),
                   "attorneys_approved": sum(1 for a in lawyers if a.status == "approved"),
                   "attorneys_pending": sum(1 for a in lawyers if a.status == "pending"),
                   "suspended": sum(1 for u in users if u.suspended_at is not None)},
        "claims": {"total": len(claims_q), "by_status": dict(funnel), "active": len(active),
                   "pipeline_fee_cents": pipeline_fees, "recovered_cents": recovered, "payouts_due_cents": payouts_due},
        "alerts": alerts,
    }


# --- Records browser ---------------------------------------------------------------------------------------

def _records_query(q: str, state: str, county: str, status_: str, min_cents: int):
    from .models import SurplusRecord
    from .normalize import normalize_name
    stmt = select(SurplusRecord)
    if status_:
        stmt = stmt.where(SurplusRecord.status == status_)
    if state:
        stmt = stmt.where(SurplusRecord.state == state.upper())
    if county:
        stmt = stmt.where(func.lower(SurplusRecord.county) == county.lower().removesuffix(" county").strip())
    if min_cents:
        stmt = stmt.where(SurplusRecord.amount_cents >= min_cents)
    if q.strip():
        like = f"%{normalize_name(q)}%"
        stmt = stmt.where((SurplusRecord.owner_name_norm.like(like)) | (SurplusRecord.reference.ilike(f"%{q.strip()}%")))
    return stmt


def _record_row(r, claimed: dict) -> dict:
    from .legal import deadline_for
    d = deadline_for(r.state, r.sale_date)
    return {"id": r.id, "state": r.state, "county": r.county, "reference": r.reference, "owner_name": r.owner_name,
            "owner_address": r.owner_address, "amount_cents": r.amount_cents, "sale_type": r.sale_type,
            "sale_date": r.sale_date.isoformat() if r.sale_date else None, "status": r.status, "source": r.source,
            "first_seen": _aware(r.first_seen).isoformat(), "last_seen": _aware(r.last_seen).isoformat(),
            "deadline": d.isoformat() if d else None, "claims": claimed.get(r.id, 0), "source_url": r.source_url}


@router.get("/admin/records")
def admin_records(scope: Admin, session: DbSession, q: str = "", state: str = "", county: str = "",
                  status_: str = "listed", min_cents: int = 0, sort: str = "amount", page: int = 1,
                  per_page: int = 50) -> dict:
    """County surplus records (public data). Search by owner or reference; filter and sort."""
    from .models import SurplusRecord
    stmt = _records_query(q, state, county, status_, min_cents)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    order = {"amount": SurplusRecord.amount_cents.desc(), "newest": SurplusRecord.first_seen.desc(),
             "sale_date": SurplusRecord.sale_date.asc(), "owner": SurplusRecord.owner_name_norm.asc()}.get(sort)
    per_page = max(1, min(per_page, 200))
    rows = session.scalars(stmt.order_by(order if order is not None else SurplusRecord.id)
                           .offset((max(page, 1) - 1) * per_page).limit(per_page)).all()
    claimed = dict(session.execute(select(Claim.record_id, func.count()).where(
        Claim.record_id.in_([r.id for r in rows])).group_by(Claim.record_id)).all()) if rows else {}
    return {"total": total, "page": page, "per_page": per_page, "records": [_record_row(r, claimed) for r in rows]}


def _csv(rows: list[dict], name: str) -> Response:
    import csv
    import io
    out = io.StringIO()
    if rows:
        w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in r.items()})
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@router.get("/admin/records.csv")
def admin_records_csv(scope: Admin, session: DbSession, client: Client, q: str = "", state: str = "",
                      county: str = "", status_: str = "listed", min_cents: int = 0):
    rows = session.scalars(_records_query(q, state, county, status_, min_cents)).all()
    claimed = dict(session.execute(select(Claim.record_id, func.count()).group_by(Claim.record_id)).all())
    _log(session, "admin.records_exported", client, rows=len(rows))
    session.commit()
    return _csv([_record_row(r, claimed) for r in rows], "surpay-records.csv")


@router.get("/admin/claims.csv")
def admin_claims_csv(scope: Admin, session: DbSession, client: Client):
    """One row per claim (no ID numbers or documents)."""
    rows = []
    for c in session.scalars(select(Claim).order_by(Claim.id)):
        if scope.demo and not is_demo_claim(c):
            continue
        shown = not scope.demo or is_demo_user(c.user)
        lawyer = c.attorney.attorney if c.attorney is not None and c.attorney.attorney is not None else None
        rows.append({"ref": f"SP-{c.id:06d}", "status": c.status, "created": _aware(c.created_at).date().isoformat(),
                     "claimant": c.user.full_name if shown else "(tester)", "email": c.user.email if shown else "",
                     "county": f"{c.record.county} County, {c.record.state}", "record": c.record.reference,
                     "amount": c.record.amount_cents / 100, "fee_pct": c.fee_pct,
                     "attorney": lawyer.full_name if lawyer else "", "assignment": c.assignment_status,
                     "attorney_fee": c.attorney_fee_cents / 100, "payout": c.payout_status,
                     "for_relative": c.relative.full_name if c.relative and shown else ""})
    _log(session, "admin.claims_exported", client, rows=len(rows))
    session.commit()
    return _csv(rows, "surpay-claims.csv")


@router.post("/admin/sources/{name}/scrape")
def admin_scrape_now(name: str, scope: Admin, session: DbSession, client: Client) -> dict:
    """Refresh one county list now (runs in the background; check the overview in a minute)."""
    import threading

    from .db import SessionLocal
    from .ingest import run_source
    from .scrapers import SOURCES
    scope.read_only()
    if name not in SOURCES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown source")

    def work():
        with SessionLocal() as s:
            run_source(s, name)

    threading.Thread(target=work, daemon=True).start()
    _log(session, "admin.scrape_started", client, source=name)
    session.commit()
    return {"ok": True, "message": f"Refreshing {name}. Reload the overview in a minute."}


# --- People: search, suspend --------------------------------------------------------------------------------

def _user_row(u: User) -> dict:
    i = u.identity
    return {"id": u.id, "email": u.email, "name": u.full_name, "role": u.role,
            "created": _aware(u.created_at).date().isoformat(),
            "identity": i.review_status if i else None, "claims": len(u.claims),
            "attorney": None if u.attorney is None else {"status": u.attorney.status, "bar": f"{u.attorney.bar_state} #{u.attorney.bar_number}",
                                                         "counties": u.attorney.counties, "available": u.attorney.available},
            "suspended": u.suspended_at is not None, "suspended_reason": u.suspended_reason,
            "deletion_requested": u.deletion_requested_at is not None}


@router.get("/admin/users")
def admin_users(scope: Admin, session: DbSession, q: str = "", role: str = "", limit: int = 100) -> list[dict]:
    stmt = select(User).order_by(User.id.desc())
    if role:
        stmt = stmt.where(User.role == role)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like) | func.lower(User.full_name).like(like))
    rows = session.scalars(stmt.limit(min(limit, 500))).all()
    if scope.demo:
        rows = [u for u in rows if is_demo_user(u) or (u.attorney is not None and is_demo_attorney(u.attorney))]
    return [_user_row(u) for u in rows]


@router.post("/admin/users/{user_id}/suspend")
def admin_suspend(user_id: int, body: AdminIdentityIn, scope: Admin, session: DbSession, client: Client) -> dict:
    """decision "approved" = lift the suspension, "rejected" = suspend (signs them out everywhere)."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    scope.check(is_demo_user(user) or (user.attorney is not None and is_demo_attorney(user.attorney)))
    if body.decision == "rejected":
        if not body.note.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give a reason (kept in the audit log)")
        user.suspended_at, user.suspended_reason = _now(), body.note.strip()
        user.token_version = (user.token_version or 0) + 1
        if user.attorney is not None:  # their open cases go to another attorney
            for c in session.scalars(select(Claim).where(Claim.attorney_id == user.id,
                                                         Claim.assignment_status.in_(("offered", "accepted")))):
                if not attorneys.is_closed(c):
                    attorneys.decline(session, c, user.id,
                                      reason="Your attorney is no longer available. We're finding you another one.")
    else:
        user.suspended_at, user.suspended_reason = None, ""
    _log(session, "admin.user_suspended" if body.decision == "rejected" else "admin.user_reinstated", client,
         "user", user.id, reason=body.note)
    session.commit()
    attorneys.assign_ready(session)
    return _user_row(user)


# --- Staff-only notes on a claim ---------------------------------------------------------------------------

@router.get("/admin/claims/{claim_id}/notes")
def admin_notes(claim_id: int, scope: Admin, session: DbSession) -> list[dict]:
    claim = _claim(session, claim_id, scope)
    return [{"id": n.id, "body": n.body, "at": _aware(n.created_at).isoformat()} for n in claim.staff_notes]


@router.post("/admin/claims/{claim_id}/notes")
def admin_add_note(claim_id: int, body: AdminStatusIn, scope: Admin, session: DbSession, client: Client) -> list[dict]:
    """Uses the note field only. Never shown to the client or the attorney."""
    from .models import StaffNote
    claim = _claim(session, claim_id, scope)
    if not body.note.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Write a note")
    claim.staff_notes.append(StaffNote(body=body.note.strip()[:2000], created_at=_now()))
    _log(session, "admin.note_added", client, "claim", claim.id)
    session.commit()
    return admin_notes(claim_id, scope, session)
