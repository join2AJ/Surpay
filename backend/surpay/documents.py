"""Documents an attorney asks the client for, with what each one is and where to get it."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Claim, DocumentRequest, Notification

KINDS: dict[str, tuple[str, str]] = {
    "w9": ("IRS Form W-9", "The county needs it to issue your payment. Download it from irs.gov/w9, fill it in and "
                           "sign it, then take a photo."),
    "deed": ("Deed to the property", "The recorded deed showing you as owner. The county recorder's office or "
                                     "website can provide a copy."),
    "tax_bill": ("Property tax bill", "Any tax bill for the property in your name, from before the sale."),
    "utility_bill": ("Utility bill", "A bill sent to you at the property (power, water, gas, phone)."),
    "bank_statement": ("Bank statement", "A statement showing your name and the property address. You may cover "
                                          "account numbers."),
    "death_certificate": ("Death certificate", "A certified copy for the former owner."),
    "probate": ("Probate or heirship documents", "Letters of administration, the will, or an affidavit of heirship."),
    "notarized_affidavit": ("Signed, notarized affidavit", "Your attorney will send it in the messages; sign it "
                                                           "in front of a notary and photograph every page."),
    "photo_id": ("A clearer photo ID", "Both sides, all four corners visible, no glare."),
    "other": ("Other document", "See your attorney's note."),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def request_out(r: DocumentRequest) -> dict:
    label, hint = KINDS.get(r.kind, KINDS["other"])
    return {"id": r.id, "kind": r.kind, "label": label, "hint": hint, "note": r.note, "status": r.status,
            "review_note": r.review_note, "requested_at": r.requested_at,
            "uploaded_at": r.uploaded_at, "has_file": r.file is not None}


def create(session: Session, claim: Claim, attorney_id: int, kind: str, note: str) -> DocumentRequest:
    if kind not in KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown document type")
    r = DocumentRequest(claim_id=claim.id, attorney_id=attorney_id, kind=kind, note=note.strip(), requested_at=_now())
    session.add(r)
    session.add(Notification(user_id=claim.user_id, kind="document_request",
                             title=f"Your attorney needs: {KINDS[kind][0]}",
                             body=(note.strip() or KINDS[kind][1])[:200], claim_id=claim.id))
    return r


def upload(session: Session, claim: Claim, r: DocumentRequest, encrypted: bytes) -> None:
    if r.status == "accepted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Your attorney already accepted this document")
    r.file, r.status, r.uploaded_at, r.review_note = encrypted, "uploaded", _now(), ""
    if claim.attorney_id:
        session.add(Notification(user_id=claim.attorney_id, kind="document_uploaded",
                                 title=f"Client uploaded: {KINDS.get(r.kind, KINDS['other'])[0]}",
                                 body=f"Case #{claim.id}", claim_id=claim.id))


def review(session: Session, claim: Claim, r: DocumentRequest, decision: str, note: str) -> None:
    if r.status != "uploaded":
        raise HTTPException(status.HTTP_409_CONFLICT, "Nothing uploaded to review yet")
    r.status, r.review_note = decision, note.strip()
    if decision == "rejected":
        session.add(Notification(user_id=claim.user_id, kind="document_request",
                                 title=f"Please upload again: {KINDS.get(r.kind, KINDS['other'])[0]}",
                                 body=(note.strip() or "Your attorney couldn't use this copy.")[:200], claim_id=claim.id))
