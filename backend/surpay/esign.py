"""The registry of signed documents and the evidence behind each signature.

Every document signed in Surpay (agreement, W-9, affidavit) is kept as the exact PDF signed,
encrypted, under a fingerprint: the first 16 characters of the PDF's SHA-256 (the agreement keeps the
fingerprint of its text, as shown on screen). Anyone holding a copy can check it against the record.
Each signing is an entry in the tamper-evident audit trail, with the time (in UTC and the signer's
own time zone), IP address, device, and when the signer confirmed the codes sent to their email and
phone.
"""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit, crypto
from .audit import ClientInfo
from .models import SignedDocument, User


def stamp(at: datetime | None, tz: str = "") -> str:
    """'Oct 11, 2026, 3:42 PM EDT (19:42 UTC)'."""
    if at is None:
        return ""
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    utc = at.astimezone(timezone.utc)
    try:
        local = at.astimezone(ZoneInfo(tz)) if tz else None
    except Exception:  # noqa: BLE001
        local = None
    if local is None:
        return f"{utc:%b} {utc.day}, {utc:%Y}, {utc:%H:%M} UTC"
    hour = local.strftime("%I").lstrip("0")
    return f"{local:%b} {local.day}, {local:%Y}, {hour}:{local:%M %p} {local.tzname()} ({utc:%H:%M} UTC)"


def register(session: Session, *, kind: str, title: str, user: User, claim_id: int | None, pdf: bytes,
             signer_name: str, client: ClientInfo, data: dict | None = None, evidence: dict | None = None,
             fingerprint: str | None = None, signed_at: datetime | None = None) -> SignedDocument:
    sha = fingerprint or crypto.sha256_hex(pdf)
    signed_at = signed_at or datetime.now(timezone.utc)
    ev = evidence or {}
    doc = SignedDocument(
        doc_id=sha[:16], sha256=sha, kind=kind, title=title, user_id=user.id, claim_id=claim_id,
        pdf=crypto.encrypt(pdf), data=json.dumps(data or {}), signer_name=signer_name, signed_at=signed_at,
        signer_tz=client.time_zone, ip_address=client.ip[:64], device_id=client.device_id[:128],
        device_info=client.device_info[:255], email=ev.get("email", ""), email_verified_at=ev.get("email_verified_at"),
        phone=ev.get("phone", ""), phone_verified_at=ev.get("phone_verified_at"))
    existing = session.scalar(select(SignedDocument).where(SignedDocument.doc_id == doc.doc_id))
    if existing is not None:
        return existing  # the very same document signed again: keep the first record
    session.add(doc)
    session.flush()
    entry = audit.record(session, "document.signed", actor_id=user.id, entity_type="signed_document",
                         entity_id=doc.id, client=client,
                         details={"doc_id": doc.doc_id, "sha256": sha, "kind": kind, "claim_id": claim_id,
                                  "signer": signer_name, "time_zone": client.time_zone,
                                  "email_verified_at": _iso(ev.get("email_verified_at")),
                                  "phone_verified_at": _iso(ev.get("phone_verified_at"))})
    session.flush()
    doc.audit_id = entry.id
    return doc


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def out(doc: SignedDocument, full: bool = False) -> dict:
    o = {"doc_id": doc.doc_id, "kind": doc.kind, "title": doc.title, "claim_id": doc.claim_id,
         "signer_name": doc.signer_name, "signed_at": doc.signed_at, "signed_at_display": stamp(doc.signed_at, doc.signer_tz),
         "time_zone": doc.signer_tz, "two_factor": bool(doc.email_verified_at and doc.phone_verified_at)}
    if full:
        o.update({"sha256": doc.sha256, "ip_address": doc.ip_address, "device": doc.device_info,
                  "device_id": doc.device_id, "email": doc.email, "email_verified_at": doc.email_verified_at,
                  "phone": doc.phone, "phone_verified_at": doc.phone_verified_at, "audit_id": doc.audit_id,
                  "user_id": doc.user_id})
    return o


def find(session: Session, doc_id: str) -> SignedDocument | None:
    return session.scalar(select(SignedDocument).where(SignedDocument.doc_id == doc_id.strip().lower()[:16]))
