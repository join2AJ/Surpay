"""Inviting owners we found to claim: printed letters, emails and in-app notices, each with an
invitation code they enter when they sign up (so we know the letter worked), and an opt-out.

Letters don't state the amount (people are rightly wary of letters promising money): they name the
county office and the case so the owner can check it independently, and invite them to sign up.
"""

import io
import secrets
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, delivery
from .filing_methods import method_for
from .models import OwnerContact, Outreach, SurplusRecord
from .trace import person_name

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


def new_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(8))


def link(code: str) -> str:
    return f"{config.PUBLIC_URL}/i/{code}"


def create(session: Session, r: SurplusRecord, channel: str, contact: OwnerContact | None) -> Outreach:
    if channel not in ("letter", "email", "in_app"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose letter, email or in_app")
    if contact is not None and contact.do_not_contact:
        raise HTTPException(status.HTTP_409_CONFLICT, "This person asked not to be contacted")
    if any(c.do_not_contact for c in session.scalars(select(OwnerContact).where(OwnerContact.record_id == r.id))):
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone at this record asked not to be contacted")
    if channel == "email" and (contact is None or contact.kind != "email"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick an email address")
    if channel == "letter" and (contact is None or contact.kind != "address"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pick a mailing address")
    o = Outreach(record_id=r.id, contact_id=contact.id if contact else None, channel=channel, code=new_code())
    session.add(o)
    session.flush()
    if channel == "email":
        sent = delivery.send_email(contact.value, f"Funds from a property sale in {r.county} County may be yours",
                                   email_text(r, o.code))
        o.status, o.sent_at = ("sent", datetime.now(timezone.utc)) if sent else ("failed", None)
    return o


def _greeting(r: SurplusRecord) -> str:
    name, deceased = person_name(r.owner_name)
    if deceased:
        return f"To the family of {name or r.owner_name.title()},"
    return f"Dear {name or r.owner_name.title()},"


def _holder(r: SurplusRecord) -> str:
    return method_for(r.state, r.county).get("where") or f"{r.county} County, {r.state}"


def body_paragraphs(r: SurplusRecord, code: str) -> list[str]:
    sale = "tax sale" if r.sale_type == "tax_sale" else "foreclosure sale"
    when = f" on {r.sale_date:%B %d, %Y}" if r.sale_date else ""
    return [
        f"Public records show that {_holder(r)} may be holding money left over from the {sale} of a property{when} "
        f"(county reference {r.reference}). When a property sells for more than was owed, the extra money belongs to "
        "the former owner, or to their heirs.",
        f"{config.COMPANY_NAME} helps owners claim these funds. We verify your identity, and a licensed attorney in your "
        "state prepares and files the claim. There is nothing to pay upfront; a fee applies only if money is recovered.",
        f"To see the details, get the {config.COMPANY_NAME} app and enter invitation code {code} when you sign up, or "
        f"visit {link(code)}. You can also confirm this record with the county office directly.",
        f"Claims have deadlines set by law, so please don't wait. If you'd rather not hear from us again, visit "
        f"{config.PUBLIC_URL}/optout/{code}.",
    ]


def email_text(r: SurplusRecord, code: str) -> str:
    footer = f"\n\n{config.COMPANY_NAME}" + (f", {config.COMPANY_ADDRESS}" if config.COMPANY_ADDRESS else "")
    return "\n\n".join([_greeting(r), *body_paragraphs(r, code), "Kind regards,"]) + footer


def letters_pdf(session: Session, items: list[Outreach]) -> bytes:
    """One letter per page, ready to print and post (address at the top for a window envelope)."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    body = ParagraphStyle("lb", parent=styles["BodyText"], fontSize=11, leading=15, spaceAfter=8)
    small = ParagraphStyle("ls", parent=body, fontSize=8.5, leading=11, textColor="#475569")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=1 * inch, rightMargin=1 * inch, topMargin=0.8 * inch,
                            bottomMargin=0.8 * inch, title=f"{config.COMPANY_NAME} letters")
    story = []
    for n, o in enumerate(items):
        r = session.get(SurplusRecord, o.record_id)
        contact = session.get(OwnerContact, o.contact_id) if o.contact_id else None
        name, _ = person_name(r.owner_name)
        story += [Paragraph(escape(config.COMPANY_NAME + (", " + config.COMPANY_ADDRESS if config.COMPANY_ADDRESS else "")), small),
                  Spacer(1, 18),
                  Paragraph(escape(name or r.owner_name.title()), body),
                  Paragraph(escape(contact.value if contact else ""), body),
                  Spacer(1, 18),
                  Paragraph(datetime.now(timezone.utc).strftime("%B %d, %Y"), body),
                  Paragraph(escape(_greeting(r)), body)]
        story += [Paragraph(escape(p), body) for p in body_paragraphs(r, o.code)]
        story += [Paragraph("Kind regards,", body), Paragraph(escape(config.COMPANY_NAME), body), Spacer(1, 20),
                  Paragraph(escape(f"Invitation code: {o.code}  ·  {link(o.code)}"), small),
                  Paragraph(escape(f"{config.COMPANY_NAME} is a technology platform, not a law firm or a government "
                                   "agency. This is not a bill."), small)]
        if n < len(items) - 1:
            story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()


def opt_out(session: Session, code: str) -> SurplusRecord | None:
    o = session.scalar(select(Outreach).where(Outreach.code == code.upper()))
    if o is None:
        return None
    for c in session.scalars(select(OwnerContact).where(OwnerContact.record_id == o.record_id)):
        c.do_not_contact = True
    for other in session.scalars(select(Outreach).where(Outreach.record_id == o.record_id)):
        other.status = "opted_out"
    return session.get(SurplusRecord, o.record_id)


def redeem(session: Session, code: str, user_id: int) -> Outreach | None:
    """A new account signed up with an invitation code."""
    o = session.scalar(select(Outreach).where(Outreach.code == code.strip().upper()))
    if o is not None and o.status != "opted_out":
        o.status, o.user_id = "signed_up", user_id
    return o
