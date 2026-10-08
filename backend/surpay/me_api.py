"""The signed-in person's notifications, family members, consents and privacy rights."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from . import audit
from .audit import ClientInfo
from .deps import Client, CurrentUser, DbSession, encrypt_image
from .models import AuditLog, Consent, Message, Notification, PreviousAddress, Relative, User
from .policies import PRIVACY_VERSION, TERMS_VERSION, privacy_text, terms_text
from .schemas import AddressOut, NotificationOut, NotificationsOut, PoliciesOut, RelativeIn, RelativeOut

router = APIRouter(tags=["me"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Consents -----------------------------------------------------------------------------------

def record_consent(session: Session, user: User, kind: str, version: str, client: ClientInfo) -> None:
    session.add(Consent(user_id=user.id, kind=kind, version=version, ip_address=client.ip[:64],
                        device_id=client.device_id[:128], accepted_at=_now()))
    audit.record(session, "consent.given", actor_id=user.id, entity_type="user", entity_id=user.id,
                 client=client, details={"kind": kind, "version": version})


def terms_current(user: User) -> bool:
    session = object_session(user)
    if session is None:
        return True
    have = {(c.kind, c.version) for c in session.scalars(
        select(Consent).where(Consent.user_id == user.id, Consent.withdrawn_at.is_(None)))}
    return ("terms", TERMS_VERSION) in have and ("privacy", PRIVACY_VERSION) in have


@router.get("/policies", response_model=PoliciesOut)
def policies():
    """Terms of Use and Privacy Notice, shown before sign-up."""
    return PoliciesOut(terms_version=TERMS_VERSION, terms=terms_text(),
                       privacy_version=PRIVACY_VERSION, privacy=privacy_text())


@router.post("/me/consents/accept-current")
def accept_current(user: CurrentUser, session: DbSession, client: Client) -> dict:
    """Accept the latest Terms and Privacy Notice (asked again after they change)."""
    if not terms_current(user):
        record_consent(session, user, "terms", TERMS_VERSION, client)
        record_consent(session, user, "privacy", PRIVACY_VERSION, client)
        session.commit()
    return {"ok": True}


# --- Notifications --------------------------------------------------------------------------------

def _notification_out(n: Notification) -> NotificationOut:
    return NotificationOut(id=n.id, kind=n.kind, title=n.title, body=n.body, claim_id=n.claim_id,
                           created_at=n.created_at, read=n.read_at is not None)


@router.get("/me/notifications", response_model=NotificationsOut)
def notifications(user: CurrentUser, session: DbSession, after_id: int = 0, limit: int = 50):
    """Newest first. The app polls with after_id to show phone notifications for new items."""
    rows = session.scalars(select(Notification).where(Notification.user_id == user.id, Notification.id > after_id)
                           .order_by(Notification.id.desc()).limit(min(limit, 100))).all()
    unread = sum(1 for n in session.scalars(select(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))))
    return NotificationsOut(items=[_notification_out(n) for n in rows], unread=unread)


@router.post("/me/notifications/read")
def read_notifications(user: CurrentUser, session: DbSession) -> dict:
    for n in session.scalars(select(Notification).where(Notification.user_id == user.id,
                                                        Notification.read_at.is_(None))):
        n.read_at = _now()
    session.commit()
    return {"ok": True}


# --- Family members (heir claims) ------------------------------------------------------------------

def relative_out(r: Relative) -> RelativeOut:
    return RelativeOut(
        id=r.id, full_name=r.full_name, other_names=r.other_names or [], relationship=r.relation,
        basis=r.basis, date_of_death=r.date_of_death, review_status=r.review_status, review_note=r.review_note,
        addresses=[AddressOut(id=a.id, street=a.street, city=a.city, state=a.state, zip=a.zip, county=a.county)
                   for a in r.user.addresses if a.relative_id == r.id],
        submitted_at=r.submitted_at,
    )


@router.get("/me/relatives", response_model=list[RelativeOut])
def my_relatives(user: CurrentUser):
    return [relative_out(r) for r in user.relatives]


@router.post("/me/relatives", response_model=RelativeOut, status_code=status.HTTP_201_CREATED)
def add_relative(body: RelativeIn, user: CurrentUser, session: DbSession, client: Client):
    """Search for a family member's surplus. Unlocks after staff check the documents.

    You need your own verified ID first, then proof of how you're related and of your right
    to act (heir, power of attorney or guardian).
    """
    if user.identity is None or user.identity.review_status != "approved":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verify your own identity first")
    if not body.consent:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please confirm the documents are genuine")
    if body.basis == "heir" and (not body.death_certificate_b64 or body.date_of_death is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "To claim as an heir, add the date of death and a photo of the death certificate")
    if body.basis in ("power_of_attorney", "guardian") and not body.authority_document_b64:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Add a photo of the power of attorney or guardianship order")
    if len(user.relatives) >= 10:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can add up to 10 family members")
    rel = Relative(
        full_name=body.full_name.strip(), other_names=[n.strip() for n in body.other_names if n.strip()],
        relation=body.relationship, basis=body.basis, date_of_death=body.date_of_death,
        death_certificate=encrypt_image(body.death_certificate_b64, "Death certificate") if body.death_certificate_b64 else None,
        relationship_proof=encrypt_image(body.relationship_proof_b64, "Relationship proof"),
        authority_document=encrypt_image(body.authority_document_b64, "Authority document") if body.authority_document_b64 else None,
    )
    user.relatives.append(rel)
    session.flush()
    for a in body.addresses:
        user.addresses.append(PreviousAddress(**a.model_dump(), relative_id=rel.id))
    audit.record(session, "relative.submitted", actor_id=user.id, entity_type="relative", entity_id=rel.id,
                 client=client, details={"name": rel.full_name, "relationship": rel.relation, "basis": rel.basis})
    session.commit()
    session.refresh(rel)
    return relative_out(rel)


@router.delete("/me/relatives/{relative_id}")
def remove_relative(relative_id: int, user: CurrentUser, session: DbSession, client: Client) -> dict:
    rel = next((r for r in user.relatives if r.id == relative_id), None)
    if rel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if any(c.relative_id == rel.id for c in user.claims):
        raise HTTPException(status.HTTP_409_CONFLICT, "There's a claim for this family member; withdraw it first")
    user.addresses = [a for a in user.addresses if a.relative_id != rel.id]
    user.relatives.remove(rel)
    audit.record(session, "relative.removed", actor_id=user.id, entity_type="relative", entity_id=relative_id,
                 client=client)
    session.commit()
    return {"ok": True}


# --- Privacy rights: access / portability, erasure ------------------------------------------------

@router.get("/me/export")
def export_my_data(user: CurrentUser, session: DbSession, client: Client) -> dict:
    """Everything Surpay holds about you, as JSON (images listed, not included)."""
    i = user.identity
    data = {
        "exported_at": _now().isoformat(),
        "account": {"email": user.email, "full_name": user.full_name, "other_names": user.other_names or [],
                    "role": user.role, "created_at": user.created_at.isoformat()},
        "identity": None if i is None else {
            "legal_name": i.legal_name, "date_of_birth": i.date_of_birth.isoformat(), "ssn_last4": i.ssn_last4,
            "phone": i.phone, "address": f"{i.street}, {i.city}, {i.state} {i.zip}", "id_type": i.id_type,
            "documents_held": [k for k in ("id_front", "id_back", "selfie") if getattr(i, k)],
            "review_status": i.review_status, "submitted_at": i.submitted_at.isoformat()},
        "homes": [{"street": a.street, "city": a.city, "state": a.state, "zip": a.zip, "county": a.county,
                   "relative_id": a.relative_id} for a in user.addresses],
        "family_members": [{"id": r.id, "name": r.full_name, "relationship": r.relation, "basis": r.basis,
                            "review_status": r.review_status} for r in user.relatives],
        "claims": [{
            "id": c.id, "status": c.status, "county": c.record.county, "state": c.record.state,
            "reference": c.record.reference, "amount_cents": c.record.amount_cents, "fee_pct": c.fee_pct,
            "history": [{"status": e.status, "note": e.note, "at": e.created_at.isoformat()} for e in c.events],
            "agreement": None if c.agreement is None else {
                "version": c.agreement.version, "text": c.agreement.text, "signed_at": c.agreement.signed_at.isoformat(),
                "typed_name": c.agreement.signature_name, "document_sha256": c.agreement.document_sha256,
                "ip_address": c.agreement.ip_address, "device": c.agreement.device_info},
            "messages": [{"from": m.sender_role, "at": m.created_at.isoformat(), "text": m.body} for m in c.messages],
        } for c in user.claims],
        "consents": [{"kind": c.kind, "version": c.version, "accepted_at": c.accepted_at.isoformat(),
                      "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None}
                     for c in session.scalars(select(Consent).where(Consent.user_id == user.id))],
        "activity": [audit.entry_out(e) for e in session.scalars(
            select(AuditLog).where(AuditLog.actor_id == user.id).order_by(AuditLog.id))],
    }
    audit.record(session, "data.exported", actor_id=user.id, entity_type="user", entity_id=user.id, client=client)
    session.commit()
    return data


_KEEP_STATUSES = {"agreement_signed", "identity_verified", "attorney_assigned", "filed", "hearing_pending",
                  "approved", "paid", "denied"}


@router.post("/me/delete")
def delete_my_account(user: CurrentUser, session: DbSession, client: Client) -> dict:
    """Withdraw consent and erase the account.

    With no signed agreement, everything is deleted now. Signed claims must be kept (legal and
    audit obligations, and the attorney's file), so the account is closed, consents are
    withdrawn, and staff erase it when the retention period ends.
    """
    now = _now()
    for c in session.scalars(select(Consent).where(Consent.user_id == user.id, Consent.withdrawn_at.is_(None))):
        c.withdrawn_at = now
    user.token_version = (user.token_version or 0) + 1  # signs out every device
    if any(c.status in _KEEP_STATUSES or c.agreement is not None for c in user.claims):
        user.deletion_requested_at = now
        audit.record(session, "account.deletion_requested", actor_id=user.id, entity_type="user",
                     entity_id=user.id, client=client)
        session.commit()
        return {"deleted": False,
                "message": "Your account is closed. Because you signed a claim agreement, we must keep that "
                           "claim's records for up to 7 years; everything else will be erased. "
                           "Contact us if you have questions."}
    uid = user.id
    for n in session.scalars(select(Notification).where(Notification.user_id == uid)):
        session.delete(n)
    for c in session.scalars(select(Consent).where(Consent.user_id == uid)):
        session.delete(c)
    for m in session.scalars(select(Message).where(Message.sender_id == uid)):
        session.delete(m)
    session.delete(user)
    audit.record(session, "account.erased", actor_id=uid, entity_type="user", entity_id=uid, client=client)
    session.commit()
    return {"deleted": True, "message": "Your account and data have been deleted."}

