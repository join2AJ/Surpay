"""Two-factor codes, forms the client fills in and signs in the app, and their signed documents."""

import base64
import json
import re

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import audit, claims, crypto, documents, esign, forms, verification
from .deps import Client, CurrentUser, DbSession
from .models import DocumentRequest, SignedDocument

router = APIRouter(tags=["forms"])

STATE_NAMES = {"AL": "Alabama", "AZ": "Arizona", "CA": "California", "FL": "Florida", "GA": "Georgia",
               "OH": "Ohio", "SC": "South Carolina", "TX": "Texas"}


class CodeStart(BaseModel):
    channel: str


class CodeConfirm(BaseModel):
    channel: str
    code: str = Field(min_length=4, max_length=8)


class FormIn(BaseModel):
    fields: dict = Field(default_factory=dict)
    signature_png_b64: str
    # The signer ticked "I certify..." for this form (the W-9's perjury certification, or the affidavit oath).
    certify: bool = False


@router.get("/me/verify")
def verify_state(user: CurrentUser, session: DbSession) -> dict:
    return verification.state(session, user)


@router.post("/me/verify/start")
def verify_start(body: CodeStart, user: CurrentUser, session: DbSession, client: Client) -> dict:
    out = verification.start(session, user, body.channel)
    audit.record(session, "verify.code_sent", actor_id=user.id, entity_type="user", entity_id=user.id, client=client,
                 details={"channel": body.channel, "to": out["sent_to"], "delivered": out["sent"]})
    session.commit()
    return out


@router.post("/me/verify/confirm")
def verify_confirm(body: CodeConfirm, user: CurrentUser, session: DbSession, client: Client) -> dict:
    out = verification.confirm(session, user, body.channel, body.code)
    audit.record(session, "verify.confirmed", actor_id=user.id, entity_type="user", entity_id=user.id, client=client,
                 details={"channel": body.channel})
    session.commit()
    return out


def _claim(user, claim_id: int):
    claim = next((c for c in user.claims if c.id == claim_id), None)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    return claim


def prefill(claim, kind: str) -> dict:
    """What we already know, so the client only checks and completes it."""
    from .filing_methods import method_for
    u, i, r = claim.user, claim.user.identity, claim.record
    holder = method_for(r.state, r.county).get("where") or f"{r.county} County, {r.state}"
    base = {"name": i.legal_name if i else u.full_name,
            "address": i.street if i else "", "city_state_zip": f"{i.city}, {i.state} {i.zip}" if i else "",
            "ssn_last4_on_file": i.ssn_last4 if i else ""}
    if kind == "w9":
        return {**base, "classification": "individual", "requester": holder,
                "account_numbers": f"SP-{claim.id:06d} / {r.reference}"[:80]}
    common = {"name": base["name"], "current_address": f"{base['address']}, {base['city_state_zip']}".strip(", "),
              "property_address": r.owner_address or "", "reference": r.reference,
              "attorney": claim.attorney.attorney.full_name if claim.attorney and claim.attorney.attorney
              and claim.assignment_status == "accepted" else ""}
    if kind == "heirship_affidavit" and claim.relative is not None:
        rel = claim.relative
        return {**common, "deceased": rel.full_name, "relationship": rel.relation,
                "date_of_death": rel.date_of_death.isoformat() if rel.date_of_death else "", "heirs": "", "will": "",
                "probate": ""}
    return {**common, "other_owners": "", "liens": ""}


@router.get("/me/claims/{claim_id}/forms/{kind}")
def form_prefill(claim_id: int, kind: str, user: CurrentUser) -> dict:
    if kind not in documents.FILLABLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown form")
    claim = _claim(user, claim_id)
    return {"kind": kind, "title": forms.KINDS[kind], "fields": prefill(claim, kind),
            "certification": CERTIFICATIONS[kind]}


CERTIFICATIONS = {
    "w9": "Under penalties of perjury, I certify that: (1) the number shown on this form is my correct taxpayer "
          "identification number; (2) I am not subject to backup withholding because I am exempt, I have not been "
          "notified by the IRS that I am subject to backup withholding, or the IRS has notified me that I am no "
          "longer subject to it; (3) I am a U.S. citizen or other U.S. person; and (4) any FATCA code entered is "
          "correct.",
    "ownership_affidavit": "I swear that the statements in this affidavit are true, and I understand that a false "
                           "statement may be punished as perjury.",
    "heirship_affidavit": "I swear that the statements in this affidavit are true, and I understand that a false "
                          "statement may be punished as perjury.",
}


def _req(claim, kind: str) -> DocumentRequest:
    documents.ensure_checklist(None, claim)
    r = next((r for r in claim.document_requests if r.kind == kind and r.status != "accepted"), None)
    if r is None:
        r = next((r for r in claim.document_requests if r.kind == kind), None)
        if r is not None and r.status == "accepted":
            raise HTTPException(status.HTTP_409_CONFLICT, "Your attorney already accepted this form")
        r = DocumentRequest(kind=kind, source="checklist")
        claim.document_requests.append(r)
    return r


@router.post("/me/claims/{claim_id}/forms/{kind}")
def sign_form(claim_id: int, kind: str, body: FormIn, user: CurrentUser, session: DbSession, client: Client) -> dict:
    from .api import claim_out
    if kind not in documents.FILLABLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown form")
    claim = _claim(user, claim_id)
    if not body.certify:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tick the certification to sign")
    evidence = verification.require_fresh(session, user)
    try:
        signature = base64.b64decode(body.signature_png_b64, validate=True)
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Draw your signature") from None
    if len(signature) < 60 or not signature.startswith(b"\x89PNG"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Draw your signature")

    known = prefill(claim, kind)
    d = {k: str(v).strip() for k, v in {**known, **body.fields}.items() if not k.endswith("_on_file")}
    ident = user.identity
    legal = ident.legal_name if ident else user.full_name
    if not claims.names_match(d.get("name", ""), legal):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"The name must match the name on your ID ({legal})")
    d["name"] = legal
    r = claim.record
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if kind == "w9":
        ssn = re.sub(r"\D", "", d.get("ssn", ""))
        if len(ssn) != 9 or ssn.startswith(("000", "666")) or ssn[3:5] == "00":  # 9xx is an ITIN: allowed
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter your full 9-digit Social Security number (or ITIN)")
        if ident and ident.ssn_last4 and ident.ssn_last4 != "0000" and ssn[-4:] != ident.ssn_last4:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "That number doesn't end in the last 4 digits you gave when you verified your ID")
        if not d.get("address") or not d.get("city_state_zip"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter your address")
        d["ssn"] = ssn
        d["classification"] = "trust_estate" if d.get("classification") == "trust_estate" else "individual"
    else:
        d.update(state_name=STATE_NAMES.get(r.state, r.state), county=r.county,
                 sale=f"{'tax sale' if r.sale_type == 'tax_sale' else 'foreclosure sale'}"
                      + (f" on {r.sale_date:%B %d, %Y}" if r.sale_date else ""),
                 amount=f"{r.amount_cents / 100:,.2f}",
                 holder=(known.get("holder") or f"{r.county} County, {r.state}"))
        from .filing_methods import method_for
        d["holder"] = method_for(r.state, r.county).get("where") or d["holder"]
        if kind == "heirship_affidavit" and not d.get("deceased"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This claim isn't for a family member")

    rows = forms.certificate_rows(legal, now, client.time_zone, client.ip, client.device_info, evidence,
                                  f"SP-{claim.id:06d}, {r.county} County, {r.state}, {r.reference}")
    build = {"w9": forms.w9_pdf, "ownership_affidavit": forms.ownership_affidavit_pdf,
             "heirship_affidavit": forms.heirship_affidavit_pdf}[kind]
    pdf = build(d, signature, now, client.time_zone, rows)
    stored = {k: v for k, v in d.items()}
    if "ssn" in stored:
        stored["ssn"] = stored["ssn"]  # kept encrypted in the registry; never returned in full
    doc = esign.register(session, kind=kind, title=forms.KINDS[kind], user=user, claim_id=claim.id, pdf=pdf,
                         signer_name=legal, client=client, data=stored, evidence=evidence, signed_at=now)
    req = _req(claim, kind)
    req.signed_document_id, req.status, req.uploaded_at, req.review_note = doc.id, "uploaded", now, ""
    session.flush()
    documents.notify_uploaded(session, claim, req)
    session.commit()
    session.refresh(claim)
    return {"document": esign.out(doc), "claim": claim_out(claim).model_dump(mode="json")}


@router.get("/me/documents")
def my_documents(user: CurrentUser, session: DbSession) -> list[dict]:
    rows = session.scalars(select(SignedDocument).where(SignedDocument.user_id == user.id)
                           .order_by(SignedDocument.id.desc()))
    return [esign.out(d) for d in rows]


@router.get("/me/documents/{doc_id}/pdf")
def my_document_pdf(doc_id: str, user: CurrentUser, session: DbSession) -> Response:
    doc = esign.find(session, doc_id)
    if doc is None or doc.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return pdf_response(doc)


def pdf_response(doc: SignedDocument) -> Response:
    return Response(crypto.decrypt(doc.pdf), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc.kind}-{doc.doc_id}.pdf"',
                             "Cache-Control": "no-store"})


def masked_data(doc: SignedDocument) -> dict:
    try:
        d = json.loads(doc.data or "{}")
    except ValueError:
        d = {}
    if "ssn" in d:
        d["ssn"] = "•••-••-" + d["ssn"][-4:]
    return d
