"""A printable claim packet (PDF) for the attorney: cover sheet with the filing steps, a draft
claimant affidavit with a notary block, the signed agreement with its signing evidence, and the
identity and family documents as exhibits."""

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import crypto
from .legal import deadline_for, filing_guide, legal_basis
from .models import Claim

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_styles["Heading1"], fontSize=16, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=_styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("body", parent=_styles["BodyText"], fontSize=9.5, leading=13)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
MONO = ParagraphStyle("mono", parent=BODY, fontName="Courier", fontSize=8, leading=10)


def _p(text: str, style=BODY) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _table(rows: list[tuple[str, str]]) -> Table:
    t = Table([[_p(k, SMALL), _p(v)] for k, v in rows], colWidths=[1.7 * inch, 4.8 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD"))]))
    return t


def _image(blob: bytes | None, max_w: float = 6 * inch, max_h: float = 4 * inch):
    if not blob:
        return _p("(not provided)", SMALL)
    try:
        data = crypto.decrypt(blob)
        img = Image(io.BytesIO(data))
        scale = min(max_w / img.imageWidth, max_h / img.imageHeight, 1)
        img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
        return img
    except Exception:  # noqa: BLE001  placeholder or unreadable image
        return _p("(image could not be rendered; download it from the case screen)", SMALL)


def build(claim: Claim) -> bytes:
    r, u = claim.record, claim.user
    i, a, rel = u.identity, claim.agreement, claim.relative
    guide, legal = filing_guide(r.state), legal_basis(r.state)
    deadline = deadline_for(r.state, r.sale_date)
    name = i.legal_name if i else u.full_name
    story: list = []

    # 1. Cover sheet
    story += [_p(f"Claim packet: case SP-{claim.id:06d}", H1),
              _p(f"Prepared {datetime.now(timezone.utc):%B %d, %Y} by Surpay for the attorney of record. "
                 "Confidential: attorney-client file.", SMALL), Spacer(1, 8)]
    story += [_p("Funds", H2), _table([
        ("County", f"{r.county} County, {r.state}"), ("Reference", r.reference),
        ("Listed owner", r.owner_name), ("Owner address on record", r.owner_address or "-"),
        ("Sale", f"{r.sale_type.replace('_', ' ')}, {r.sale_date:%B %d, %Y}" if r.sale_date else r.sale_type),
        ("Amount reported", f"${r.amount_cents / 100:,.2f}"),
        ("Approx. last day to claim", f"{deadline:%B %d, %Y}" if deadline else "See statute"),
        ("Source", r.source_url or "-")])]
    claimant_rows = [("Claimant", name), ("Other names", ", ".join(u.other_names or []) or "-")]
    if i:
        claimant_rows += [("Date of birth", i.date_of_birth.strftime("%B %d, %Y")), ("SSN (last 4)", i.ssn_last4),
                          ("Current address", f"{i.street}, {i.city}, {i.state} {i.zip}"),
                          ("ID type", i.id_type.replace("_", " "))]
    if rel:
        claimant_rows += [("Claiming for", f"{rel.full_name} ({rel.relation}; {rel.basis.replace('_', ' ')})"),
                          ("Date of death", rel.date_of_death.strftime("%B %d, %Y") if rel.date_of_death else "-")]
    claimant_rows += [("Homes listed", "; ".join(f"{h.street}, {h.city}, {h.state} {h.zip}" for h in u.addresses
                                                 if h.relative_id == (rel.id if rel else None)) or "-")]
    story += [_p("Claimant", H2), _table(claimant_rows)]
    story += [_p("Legal basis", H2), _p(f"{legal['law']}. {legal['right']}"), _p(legal["deadline"])]
    story += [_p("Where and how to file", H2), _p(f"Where: {guide['where']}"), _p(f"Online or paper: {guide['online']}")]
    story += [_p(f"{n}. {step}") for n, step in enumerate(guide["steps"], 1)]
    story += [_p("Print and sign", H2)] + [_p(f"[ ] {item}") for item in guide["print"]]
    story.append(PageBreak())

    # 2. Draft affidavit
    capacity = ""
    if rel:
        capacity = {"heir": f" I am an heir of {rel.full_name}, who died on "
                            f"{rel.date_of_death:%B %d, %Y}." if rel.date_of_death else f" I am an heir of {rel.full_name}.",
                    "power_of_attorney": f" I act for {rel.full_name} under a durable power of attorney.",
                    "guardian": f" I am the court-appointed guardian of {rel.full_name}."}.get(rel.basis, "")
    owner = rel.full_name if rel else name
    story += [_p("AFFIDAVIT OF IDENTITY AND ENTITLEMENT TO EXCESS FUNDS (DRAFT)", H1),
              _p("Attorney: adapt to the county's form and the governing statute before use.", SMALL), Spacer(1, 6),
              _p(f"STATE OF {r.state}\nCOUNTY OF {r.county.upper()}"), Spacer(1, 6),
              _p(f"I, {name}, being first duly sworn, state:"),
              _p(f"1. I am over 18 years old and competent to make this affidavit.{capacity}"),
              _p(f"2. {owner} was the record owner of the property sold in {r.county} County, {r.state} "
                 f"({r.reference}) at the time of the sale."),
              _p("3. I am entitled to the excess proceeds from that sale and I am not aware of any assignment "
                 "of them to anyone else."),
              _p("4. The copies of identification and documents attached are true and correct."),
              _p("5. I ask that the excess funds be paid to me (or as the court directs)."),
              Spacer(1, 18), _p("_______________________________\nSignature of affiant            Date"),
              Spacer(1, 18),
              _p("Sworn to and subscribed before me on ______________, 20___, by the affiant, who produced "
                 "identification.\n\n_______________________________\nNotary Public    My commission expires: "
                 "__________"),
              PageBreak()]

    # 3. Signed agreement and evidence of signing
    story.append(_p("Signed agreement and signing evidence", H1))
    if a:
        story += [_table([("Signed by (typed)", a.signature_name), ("Name on verified ID", a.legal_name_on_id or name),
                          ("Signed at (UTC)", a.signed_at.strftime("%Y-%m-%d %H:%M:%S")),
                          ("IP address", a.ip_address or "-"), ("Device", a.device_info or "-"),
                          ("Device ID", a.device_id or "-"), ("Agreement version", a.version),
                          ("SHA-256 of text", a.document_sha256 or crypto.sha256_hex(a.text))]),
                  Spacer(1, 6), _p("Drawn signature:", SMALL), _image(a.signature_image, 3 * inch, 1.2 * inch),
                  Spacer(1, 8), _p(a.text, MONO)]
    else:
        story.append(_p("Not signed yet."))
    story.append(PageBreak())

    # 4. Exhibits
    story.append(_p("Exhibits", H1))
    if i:
        story += [_p("Exhibit A: photo ID (front)", H2), _image(i.id_front)]
        if i.id_back:
            story += [_p("Exhibit A-2: photo ID (back)", H2), _image(i.id_back)]
    if rel:
        story += [_p("Exhibit B: proof of relationship", H2), _image(rel.relationship_proof)]
        if rel.death_certificate:
            story += [_p("Exhibit C: death certificate", H2), _image(rel.death_certificate)]
        if rel.authority_document:
            story += [_p("Exhibit D: authority document", H2), _image(rel.authority_document)]
    from .documents import KINDS
    for n, d in enumerate([d for d in claim.document_requests if d.file is not None and d.status != "rejected"], 1):
        story += [_p(f"Exhibit E-{n}: {KINDS.get(d.kind, KINDS['other'])[0]} (supplied by the client)", H2),
                  _image(d.file)]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                      topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                      title=f"Surpay claim packet SP-{claim.id:06d}").build(story)
    return buf.getvalue()
