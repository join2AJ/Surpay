"""The documents a claim needs: a checklist the client prepares as soon as the claim starts (forms
filled in and signed in the app, plus photos of their own papers), and anything else the attorney
asks for later. The attorney reviews each one and can send it back with a reason."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Claim, DocumentRequest, Notification

KINDS: dict[str, tuple[str, str]] = {
    "w9": ("IRS Form W-9", "The county needs it to issue your payment. Fill it in and sign it right here in the "
                           "app: we fill in the official IRS form for you."),
    "ownership_affidavit": ("Affidavit of ownership", "Your sworn statement that you owned the property and haven't "
                                                      "sold your right to the money. Fill it in and sign it in the app."),
    "heirship_affidavit": ("Affidavit of heirship", "Your sworn statement of how you're related to the owner who died "
                                                    "and who the other heirs are. Fill it in and sign it in the app."),
    "proof_of_ownership": ("Proof you owned the property", "The deed, or a property tax bill in your name from before "
                                                          "the sale. A clear photo of the whole page."),
    "proof_of_address": ("Proof you lived there", "A utility bill, bank statement or insurance letter sent to you at "
                                                  "the property. You may cover account numbers."),
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


# Filled in and signed in the app (forms.py), not photographed.
FILLABLE = ("w9", "ownership_affidavit", "heirship_affidavit")

# Why an attorney sends a document back: quick choices in the app.
REJECT_REASONS = [
    "The photo is blurry or cut off. Please retake it in good light with all four corners visible.",
    "This isn't the right document.",
    "The name doesn't match the name on your ID.",
    "The county needs this signed in front of a notary.",
    "This is too old. Please send a recent one.",
]


def checklist_kinds(claim: Claim) -> list[str]:
    """What every claim needs before filing (counties differ; the attorney adds anything else)."""
    kinds = ["w9", "heirship_affidavit" if claim.relative_id else "ownership_affidavit"]
    if not claim.relative_id:
        kinds += ["proof_of_ownership", "proof_of_address"]
    return kinds


def ensure_checklist(session: Session, claim: Claim) -> bool:
    """Add the checklist items a claim doesn't have yet. True if anything was added."""
    have = {r.kind for r in claim.document_requests}
    added = False
    for kind in checklist_kinds(claim):
        if kind not in have:
            claim.document_requests.append(DocumentRequest(kind=kind, source="checklist", requested_at=_now()))
            added = True
    return added


def _now() -> datetime:
    return datetime.now(timezone.utc)


def request_out(r: DocumentRequest) -> dict:
    label, hint = KINDS.get(r.kind, KINDS["other"])
    return {"id": r.id, "kind": r.kind, "label": label, "hint": hint, "note": r.note, "status": r.status,
            "review_note": r.review_note, "requested_at": r.requested_at,
            "uploaded_at": r.uploaded_at, "has_file": r.file is not None or r.signed_document_id is not None,
            "fill_in_app": r.kind in FILLABLE, "source": r.source or "attorney",
            "doc_id": _doc_id(r)}


def _doc_id(r: DocumentRequest) -> str | None:
    if r.signed_document_id is None:
        return None
    from sqlalchemy.orm import object_session

    from .models import SignedDocument
    s = object_session(r)
    doc = s.get(SignedDocument, r.signed_document_id) if s is not None else None
    return doc.doc_id if doc else None


def create(session: Session, claim: Claim, attorney_id: int, kind: str, note: str) -> DocumentRequest:
    if kind not in KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown document type")
    # Already on the checklist and not yet accepted: ask for it again rather than adding a second one.
    r = next((x for x in claim.document_requests if x.kind == kind and x.status != "accepted"), None)
    if r is not None:
        r.note, r.attorney_id = note.strip(), attorney_id
        if r.status == "uploaded" and note.strip():
            r.status, r.review_note = "rejected", note.strip()
    else:
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
    notify_uploaded(session, claim, r)


def notify_uploaded(session: Session, claim: Claim, r: DocumentRequest) -> None:
    if claim.attorney_id and claim.assignment_status == "accepted":
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
