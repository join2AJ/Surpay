"""Partner attorney endpoints: apply, get verified, receive cases for your counties, report progress."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from . import attorneys, audit, chat, claims, config, crypto, documents, packet
from .deps import Client, CurrentUser, DbSession, encrypt_image
from .legal import filing_guide, legal_basis
from .models import AttorneyProfile, Claim, ClaimEvent, User
from .schemas import (
    AttorneyApplyIn, AttorneyProfileOut, AttorneyUpdateIn, CaseAcceptIn, CaseDeclineIn, CaseOut, CaseStatusIn, ChatOut,
    DocumentRequestIn, DocumentReviewIn, MessageIn,
)

router = APIRouter(prefix="/attorney", tags=["attorney"])

TERMS_VERSION = "attorney-2026-10-B"


def terms_text(state: str) -> str:
    """Have ethics counsel in each state review this arrangement and wording before launch."""
    fee = config.attorney_fee_for(state) / 100
    c = config.COMPANY_NAME
    return f"""PARTNER ATTORNEY TERMS
Version {TERMS_VERSION}

These terms apply between {c} and the attorney who accepts them in the {c} app ("you").

1. CASE OFFERS
{c} may offer you surplus-funds claims for clients whose identity {c} has verified, in the counties you serve. You may accept or decline any case. Please respond within two business days; unanswered offers may be reassigned. You may hand back an accepted case until you file it.

2. ATTORNEY-CLIENT RELATIONSHIP
When you accept a case you represent the client, not {c}. You exercise independent professional judgment, and {c} does not direct or control your legal work. You are responsible for compliance with the Rules of Professional Conduct of every jurisdiction in which you practise, including rules on competence, communication, confidentiality, conflicts, fees and the sharing of fees.

3. ROLE OF {c.upper()}
{c} is a technology platform. It is not a law firm, does not practise law and is not responsible for the legal work on any case. You agree not to describe {c} as your law firm or as the client's lawyer.

4. PAYMENT
{c} pays you ${fee:,.2f} per case for your work on it, due when the case closes (funds released or claim denied). You will not charge the client any additional fee or cost for the claim without {c}'s written agreement and the client's informed consent in writing.

5. STATUS UPDATES
You will record each stage in the app as it happens: claim filed, waiting for the county or court, approved, money released, or denied. The client sees these updates.

6. CONFIDENTIALITY AND DATA
Client documents and details are provided only for the client's case. Do not copy, disclose or use them for any other purpose. Keep any downloaded copies secure and delete them when no longer needed for the file.

7. COMMUNICATION WITH CLIENTS
Communicate with clients through the app's messages. You send the first message. Do not request or share phone numbers, email addresses or other contact details in the app, and do not solicit clients for other services.

8. LICENSE AND INSURANCE
You confirm you hold an active license in good standing in {state.upper()} and professional liability insurance. Tell {c} at once if your license status changes. {c} may suspend case offers while it checks.

9. ENDING
Either party may end these terms by notice in the app. Cases you have already accepted continue until handed over or closed.
"""


def _profile_out(a: AttorneyProfile) -> AttorneyProfileOut:
    return AttorneyProfileOut(
        full_name=a.full_name, bar_state=a.bar_state, bar_number=a.bar_number, firm=a.firm, phone=a.phone,
        office_address=a.office_address, counties=a.counties or [], status=a.status, review_note=a.review_note,
        fee_per_case_cents=config.attorney_fee_for(a.bar_state), terms=terms_text(a.bar_state),
        available=a.available if a.available is not None else True,
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
def apply(body: AttorneyApplyIn, user: CurrentUser, session: DbSession, client: Client):
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
    session.flush()
    from .me_api import record_consent
    record_consent(session, user, "attorney_terms", TERMS_VERSION, client)
    audit.record(session, "attorney.applied", actor_type="attorney", actor_id=user.id, entity_type="attorney",
                 entity_id=user.attorney.id, client=client,
                 details={"bar_state": body.bar_state, "bar_number": body.bar_number.strip(),
                          "counties": user.attorney.counties})
    session.commit()
    return _profile_out(user.attorney)


@router.get("/me", response_model=AttorneyProfileOut)
def me(user: CurrentUser):
    """404 means they haven't applied yet."""
    return _profile_out(_require_attorney(user, approved=False))


@router.put("/me", response_model=AttorneyProfileOut)
def update_me(body: AttorneyUpdateIn, user: CurrentUser, session: DbSession, client: Client):
    """Update firm, phone, office and counties, or pause new case offers. Bar details need a new application."""
    from .models import CountySource
    a = _require_attorney(user, approved=False)
    changes = body.model_dump(exclude_none=True)
    if body.counties is not None:
        valid = set(session.scalars(select(CountySource.county).where(CountySource.state == a.bar_state)))
        if config.DEMO_ENABLED and a.bar_state == "OH":
            valid.add("Demo County")
        wanted = sorted({c.strip() for c in body.counties if c.strip()})
        unknown = [c for c in wanted if c not in valid]
        if unknown:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"Not a county in {a.bar_state}: {', '.join(unknown[:3])}")
        a.counties = wanted
    for field in ("firm", "phone", "office_address", "available"):
        if field in changes:
            setattr(a, field, changes[field].strip() if isinstance(changes[field], str) else changes[field])
    audit.record(session, "attorney.profile_updated", actor_type="attorney", actor_id=user.id, entity_type="attorney",
                 entity_id=a.id, client=client, details={k: v for k, v in changes.items()})
    session.commit()
    if a.available:
        attorneys.assign_ready(session)
    return _profile_out(a)


def other_claimants(c: Claim) -> int:
    """Other accounts claiming the same county record: co-owners, other heirs, or a false claim."""
    from sqlalchemy import func
    from sqlalchemy.orm import object_session
    session = object_session(c)
    if session is None:
        return 0
    return session.scalar(select(func.count()).select_from(Claim).where(
        Claim.record_id == c.record_id, Claim.id != c.id, Claim.status != "withdrawn")) or 0


def case_out(c: Claim, full: bool) -> CaseOut:
    r = c.record
    out = CaseOut(
        id=c.id, assignment_status=c.assignment_status, status=c.status, county=r.county, state=r.state,
        reference=r.reference, sale_type=r.sale_type, sale_date=r.sale_date, amount_cents=r.amount_cents,
        fee_cents=c.attorney_fee_cents, payout_status=c.payout_status, assigned_at=c.assigned_at,
        accepted_at=c.accepted_at, source_url=r.source_url, legal=legal_basis(r.state),
        filing_guide=filing_guide(r.state), chat_open=chat.thread_open(c),
        unread_messages=sum(1 for m in chat.thread(c) if m.sender_role == "claimant" and m.read_at is None),
        other_claimants=other_claimants(c),
        reference_code=f"SP-{c.id:06d}",
        document_requests=[documents.request_out(d) for d in c.document_requests] if c.assignment_status == "accepted" else [],
    )
    if full:
        from .api import on_behalf_of
        u, i, rel = c.user, c.user.identity, c.relative
        out.on_behalf_of = on_behalf_of(rel)
        # No email or phone: attorney and client talk through the app's messages.
        out.claimant = {
            "name": i.legal_name if i else u.full_name,
            "date_of_birth": i.date_of_birth.isoformat() if i else None,
            "current_address": f"{i.street}, {i.city}, {i.state} {i.zip}" if i else "",
            "other_names": u.other_names or [], "ssn_last4": i.ssn_last4 if i else "",
            "id_type": i.id_type if i else "", "has_id_back": bool(i and i.id_back),
            "homes": [f"{a.street}, {a.city}, {a.state} {a.zip} ({a.county})" for a in u.addresses
                      if a.relative_id == (rel.id if rel else None)],
            "relative": None if rel is None else {
                "name": rel.full_name, "relationship": rel.relation, "basis": rel.basis,
                "date_of_death": rel.date_of_death.isoformat() if rel.date_of_death else None,
                "documents": [k for k in ("relationship_proof", "death_certificate", "authority_document")
                              if getattr(rel, k)]},
        }
        a = c.agreement
        out.agreement = None if a is None else {
            "text": a.text, "signature_name": a.signature_name, "signed_at": a.signed_at.isoformat(),
            "fee_pct": a.fee_pct, "version": a.version, "document_sha256": a.document_sha256,
            "ip_address": a.ip_address, "device": a.device_info, "has_signature_image": a.signature_image is not None,
        }
        out.record = {"owner_name": r.owner_name, "owner_address": r.owner_address, "raw": r.raw}
        out.history = [{"status": e.status, "note": e.note, "at": e.created_at.isoformat()} for e in c.events]
    return out


def _my_case(user: User, session, case_id: int) -> Claim:
    c = session.get(Claim, case_id)
    if (c is None or c.attorney_id != user.id or c.assignment_status not in ("offered", "accepted")
            or c.status == "withdrawn"):
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
def accept_case(case_id: int, user: CurrentUser, session: DbSession, client: Client,
                body: CaseAcceptIn | None = None):
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        if body is None or not body.conflict_checked:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Confirm you've run a conflict check (no conflict with the client or other parties)")
        c.assignment_status = "accepted"
        c.accepted_at = datetime.now(timezone.utc)
        if not claims.advance(c, "attorney_assigned", f"{user.attorney.full_name} accepted your case"):
            c.events.append(ClaimEvent(status=c.status, note=f"Attorney {user.attorney.full_name} took your case",
                                       created_at=datetime.now(timezone.utc)))
        audit.record(session, "case.accepted", actor_type="attorney", actor_id=user.id, entity_type="claim",
                     entity_id=c.id, client=client, details={"conflict_checked": True})
        session.commit()
    return case_out(c, full=True)


@router.post("/cases/{case_id}/decline")
def decline_case(case_id: int, body: CaseDeclineIn, user: CurrentUser, session: DbSession, client: Client) -> dict:
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status == "accepted" and c.status not in attorneys.RETURNABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already filed; contact Surpay to hand it over")
    audit.record(session, "case.declined", actor_type="attorney", actor_id=user.id, entity_type="claim",
                 entity_id=c.id, client=client, details={"reason": body.reason})
    attorneys.decline(session, c, user.id, reason="")
    session.commit()
    return {"ok": True}


@router.post("/cases/{case_id}/status", response_model=CaseOut)
def update_case(case_id: int, body: CaseStatusIn, user: CurrentUser, session: DbSession, client: Client):
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Accept the case first")
    if attorneys.is_closed(c):
        raise HTTPException(status.HTTP_409_CONFLICT, "This case is already closed")
    allowed = attorneys.NEXT_STATUS.get(c.status, ())
    if body.status not in allowed:
        nice = ", ".join(allowed) or "nothing (the case is closed)"
        raise HTTPException(status.HTTP_409_CONFLICT, f"From “{c.status}” the next update can be: {nice}")
    claims.set_status(c, body.status, body.note)
    attorneys.settle_payout(c)
    audit.record(session, "case.status", actor_type="attorney", actor_id=user.id, entity_type="claim",
                 entity_id=c.id, client=client, details={"status": body.status, "note": body.note})
    session.commit()
    return case_out(c, full=True)


@router.get("/cases/{case_id}/documents/{kind}")
def case_document(case_id: int, kind: str, user: CurrentUser, session: DbSession):
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accept the case to see documents")
    owner = {"id_front": c.user.identity, "id_back": c.user.identity, "selfie": c.user.identity,
             "relationship_proof": c.relative, "death_certificate": c.relative, "authority_document": c.relative,
             "signature": c.agreement}.get(kind)
    attr = "signature_image" if kind == "signature" else kind
    blob = getattr(owner, attr, None) if owner is not None else None
    if blob is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not available")
    data = crypto.decrypt(blob)
    media = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return Response(data, media_type=media, headers={"Cache-Control": "no-store"})


@router.get("/cases/{case_id}/packet")
def case_packet(case_id: int, user: CurrentUser, session: DbSession, client: Client):
    """Printable PDF: cover sheet and filing steps, draft affidavit, signed agreement, exhibits."""
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accept the case to download the packet")
    pdf = packet.build(c)
    audit.record(session, "case.packet_downloaded", actor_type="attorney", actor_id=user.id, entity_type="claim",
                 entity_id=c.id, client=client)
    session.commit()
    return Response(pdf, media_type="application/pdf", headers={
        "Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="surpay-case-{c.id}.pdf"'})


@router.get("/cases/{case_id}/messages", response_model=ChatOut)
def case_messages(case_id: int, user: CurrentUser, session: DbSession):
    from .api import chat_out
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    chat.mark_read(c, "attorney")
    session.commit()
    return chat_out(c, "attorney")


@router.post("/cases/{case_id}/messages", response_model=ChatOut)
def send_case_message(case_id: int, body: MessageIn, user: CurrentUser, session: DbSession, client: Client):
    from .api import chat_out
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    msg = chat.send(session, c, user, "attorney", body.body)
    session.flush()
    audit.record(session, "message.sent", actor_type="attorney", actor_id=user.id, entity_type="message",
                 entity_id=msg.id, client=client, details={"claim_id": c.id, "body_sha256": crypto.sha256_hex(msg.body)})
    session.commit()
    return chat_out(c, "attorney")


# --- Documents the attorney needs from the client ----------------------------------------------------

def _accepted_case(user: User, session, case_id: int) -> Claim:
    _require_attorney(user)
    c = _my_case(user, session, case_id)
    if c.assignment_status != "accepted":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accept the case first")
    return c


@router.post("/cases/{case_id}/document-requests", response_model=CaseOut)
def request_document(case_id: int, body: DocumentRequestIn, user: CurrentUser, session: DbSession, client: Client):
    c = _accepted_case(user, session, case_id)
    if attorneys.is_closed(c):
        raise HTTPException(status.HTTP_409_CONFLICT, "This case is closed")
    r = documents.create(session, c, user.id, body.kind, body.note)
    session.flush()
    audit.record(session, "document.requested", actor_type="attorney", actor_id=user.id, entity_type="claim",
                 entity_id=c.id, client=client, details={"request_id": r.id, "kind": body.kind})
    session.commit()
    session.refresh(c)
    return case_out(c, full=True)


@router.get("/cases/{case_id}/document-requests/{request_id}/file")
def requested_document_file(case_id: int, request_id: int, user: CurrentUser, session: DbSession):
    c = _accepted_case(user, session, case_id)
    r = next((d for d in c.document_requests if d.id == request_id), None)
    if r is None or r.file is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not uploaded yet")
    data = crypto.decrypt(r.file)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/cases/{case_id}/document-requests/{request_id}/review", response_model=CaseOut)
def review_document(case_id: int, request_id: int, body: DocumentReviewIn, user: CurrentUser, session: DbSession,
                    client: Client):
    c = _accepted_case(user, session, case_id)
    r = next((d for d in c.document_requests if d.id == request_id), None)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    documents.review(session, c, r, body.decision, body.note)
    audit.record(session, f"document.{body.decision}", actor_type="attorney", actor_id=user.id, entity_type="claim",
                 entity_id=c.id, client=client, details={"request_id": r.id})
    session.commit()
    return case_out(c, full=True)
