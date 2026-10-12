"""Forms the client fills in and signs in the app, produced as PDFs ready to file.

- IRS Form W-9: the official form (Rev. March 2024, bundled in static/forms) with its fields filled in
  and the drawn signature and date placed on the signature line. The IRS accepts electronically
  signed W-9s when the signer's identity is verified and the signature is captured with the
  form's certification (IRS Announcement 98-27); Surpay records that evidence for each one.
- Affidavit of ownership and claim, and affidavit of heirship: sworn statements the attorney
  files with the claim. Counties that need a notary get the same PDF signed in front of one.
Each PDF ends with a signing certificate: who signed, when (their time zone and UTC), how they were
verified, and the document's fingerprint for later reference.
"""

import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import config
from .esign import stamp

W9_PATH = Path(__file__).parent / "static" / "forms" / "fw9.pdf"
W9_VERSION = "Rev. March 2024"

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("fh1", parent=_styles["Heading1"], fontSize=15, spaceAfter=6, alignment=1)
H2 = ParagraphStyle("fh2", parent=_styles["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("fbody", parent=_styles["BodyText"], fontSize=10, leading=14)
SMALL = ParagraphStyle("fsmall", parent=BODY, fontSize=8, leading=10, textColor=colors.HexColor("#475569"))

KINDS = {
    "w9": "IRS Form W-9",
    "ownership_affidavit": "Affidavit of ownership and claim to surplus funds",
    "heirship_affidavit": "Affidavit of heirship",
}


def _p(text: str, style=BODY) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _sig_image(png: bytes, w: float, h: float) -> Image | None:
    try:
        img = Image(io.BytesIO(png))
        ratio = min(w / img.imageWidth, h / img.imageHeight)
        img.drawWidth, img.drawHeight = img.imageWidth * ratio, img.imageHeight * ratio
        img.hAlign = "LEFT"
        return img
    except Exception:  # noqa: BLE001
        return None


def certificate_rows(signer: str, signed_at: datetime, tz: str, client_ip: str, device: str,
                     evidence: dict, claim_ref: str) -> list[tuple[str, str]]:
    return [
        ("Signed by", signer),
        ("Signed at", stamp(signed_at, tz)),
        ("Claim", claim_ref),
        ("Identity", "Government photo ID and selfie checked by Surpay; name on ID matches the signature"),
        ("Email confirmed", f"{evidence.get('email', '')}, {stamp(evidence.get('email_verified_at'), tz)}"),
        ("Phone confirmed", f"{evidence.get('phone', '')}, {stamp(evidence.get('phone_verified_at'), tz)}"),
        ("IP address", client_ip or "not recorded"),
        ("Device", device or "not recorded"),
        ("Record", "Kept by Surpay with a tamper-evident audit trail. The document fingerprint is listed "
                   "in the Surpay app and on request; any change to this file changes the fingerprint."),
    ]


def _certificate_page(rows: list[tuple[str, str]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    t = Table([[_p(k, SMALL), _p(v)] for k, v in rows], colWidths=[1.5 * inch, 5.3 * inch])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0"))]))
    doc.build([_p("Electronic signature certificate", H1),
               _p(f"This certificate is part of the signed document. It records how the signer was identified "
                  f"and when they signed, under the federal E-SIGN Act (15 U.S.C. § 7001) and the Uniform "
                  f"Electronic Transactions Act.", SMALL), Spacer(1, 10), t])
    return buf.getvalue()


def _join(*pdfs: bytes) -> bytes:
    w = PdfWriter()
    for pdf in pdfs:
        w.append(PdfReader(io.BytesIO(pdf)))
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


# --- IRS Form W-9 -------------------------------------------------------------------------------

def w9_pdf(d: dict, signature_png: bytes, signed_at: datetime, tz: str, cert_rows: list[tuple[str, str]]) -> bytes:
    """d: name, business_name, classification (individual | trust_estate), address, city_state_zip,
    ssn (9 digits), account_numbers, requester."""
    reader = PdfReader(str(W9_PATH))
    writer = PdfWriter()
    writer.append(reader, pages=(0, 1))  # the form page; the IRS instructions aren't filed
    ssn = d["ssn"]
    box = {"individual": ("c1_1[0]", "/1"), "trust_estate": ("c1_1[4]", "/5")}[d.get("classification", "individual")]
    values = {
        "f1_01[0]": d["name"], "f1_02[0]": d.get("business_name", ""),
        "f1_07[0]": d["address"], "f1_08[0]": d["city_state_zip"],
        "f1_09[0]": d.get("requester", "")[:120], "f1_10[0]": d.get("account_numbers", "")[:80],
        "f1_11[0]": ssn[:3], "f1_12[0]": ssn[3:5], "f1_13[0]": ssn[5:],
    }
    page = writer.pages[0]
    writer.update_page_form_field_values(page, values, auto_regenerate=False)
    # Tick the tax classification box.
    for annot in page.get("/Annots", []):
        a = annot.get_object()
        if a.get("/T") == box[0]:
            a.update({NameObject("/V"): NameObject(box[1]), NameObject("/AS"): NameObject(box[1])})
            parent = a.get("/Parent")
            if parent is not None:
                parent.get_object().update({NameObject("/V"): NameObject(box[1])})
    writer.set_need_appearances_writer(True)

    # Signature and date on the "Sign Here" line (positions measured on the March 2024 revision).
    overlay = io.BytesIO()
    c = canvas.Canvas(overlay, pagesize=LETTER)
    try:
        img = ImageReader(io.BytesIO(signature_png))
        iw, ih = img.getSize()
        h = 22
        w = min(200, iw * h / ih)
        c.drawImage(img, 152, 192, width=w, height=h, mask="auto")
    except Exception:  # noqa: BLE001
        c.setFont("Helvetica-Oblique", 12)
        c.drawString(152, 196, d["name"])
    c.setFont("Helvetica", 10)
    local = signed_at
    try:
        from zoneinfo import ZoneInfo
        local = signed_at.astimezone(ZoneInfo(tz)) if tz else signed_at
    except Exception:  # noqa: BLE001
        pass
    c.drawString(412, 196, f"{local:%m/%d/%Y}")
    c.setFont("Helvetica", 6.5)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(152, 186, f"Signed electronically {stamp(signed_at, tz)} via {config.COMPANY_NAME}; see certificate")
    c.save()
    page.merge_page(PdfReader(io.BytesIO(overlay.getvalue())).pages[0])
    writer.append(PdfReader(io.BytesIO(_certificate_page(cert_rows))))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# --- Affidavits -------------------------------------------------------------------------------------

def _affidavit(title: str, intro: str, statements: list[str], d: dict, signature_png: bytes, signed_at: datetime,
               tz: str, cert_rows: list[tuple[str, str]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch, title=title)
    story = [_p(f"STATE OF {d['state_name'].upper()}", BODY), _p(f"COUNTY OF {d['county'].upper()}", BODY),
             Spacer(1, 8), _p(title.upper(), H1), _p(intro), Spacer(1, 4)]
    story += [_p(f"{n}. {s}") for n, s in enumerate(statements, 1)]
    story += [Spacer(1, 8),
              _p("I declare under penalty of perjury under the laws of the State of "
                 f"{d['state_name']} that the foregoing is true and correct."),
              Spacer(1, 12)]
    sig = _sig_image(signature_png, 2.6 * inch, 0.7 * inch)
    if sig is not None:
        story.append(sig)
    story += [_p("______________________________________"),
              _p(f"{d['name']}, Affiant"), _p(f"Signed electronically {stamp(signed_at, tz)}", SMALL),
              Spacer(1, 18),
              _p("NOTARY (complete only if the county requires a notarized affidavit)", H2),
              _p(f"Subscribed and sworn to before me on ____________________, by {d['name']}, who is personally "
                 "known to me or produced ______________________ as identification."),
              Spacer(1, 18), _p("______________________________________   Notary Public          My commission expires: __________")]
    doc.build(story)
    return _join(buf.getvalue(), _certificate_page(cert_rows))


def ownership_affidavit_pdf(d: dict, signature_png: bytes, signed_at: datetime, tz: str,
                            cert_rows: list[tuple[str, str]]) -> bytes:
    statements = [
        f"My name is {d['name']}. I am over 18 years of age and competent to make this affidavit. "
        f"I live at {d['current_address']}.",
        f"I was an owner of record of the real property at {d['property_address']} "
        f"(county reference: {d['reference']}) at the time it was sold at the {d['sale']}.",
        f"I claim the surplus (excess) funds from that sale, listed at ${d['amount']} and held by {d['holder']}.",
        "I have not sold, assigned or transferred my right to these funds to anyone, and I have not received any "
        "part of them.",
        "To my knowledge, " + (d.get("other_owners") or "no other person held an ownership interest in the property "
                               "when it was sold, other than as stated here."),
        "Any liens on the property that I know of: " + (d.get("liens") or "none") + ".",
        f"I authorize my attorney, {d.get('attorney') or 'the attorney of record'}, to file this claim and receive "
        "notices about it on my behalf.",
    ]
    return _affidavit("Affidavit of ownership and claim to surplus funds",
                      f"Before me, the undersigned authority, personally appeared {d['name']}, who being duly sworn "
                      "deposes and says:", statements, d, signature_png, signed_at, tz, cert_rows)


def heirship_affidavit_pdf(d: dict, signature_png: bytes, signed_at: datetime, tz: str,
                           cert_rows: list[tuple[str, str]]) -> bytes:
    statements = [
        f"My name is {d['name']}. I am over 18 years of age and competent to make this affidavit. "
        f"I live at {d['current_address']}.",
        f"{d['deceased']} (the decedent) died on {d['date_of_death']}. The decedent owned the real property at "
        f"{d['property_address']} (county reference: {d['reference']}) when it was sold at the {d['sale']}.",
        f"I am the decedent's {d['relationship']}. I knew the decedent and their family history well.",
        "The decedent " + ("left a will, which " + d["will"] if d.get("will") else "did not leave a will") + ".",
        "The decedent's heirs, with their relationship, are: " + (d.get("heirs") or "as listed by me in the Surpay app") + ".",
        "No administration of the decedent's estate is pending, and none is needed other than as stated here, to the "
        "best of my knowledge." if not d.get("probate") else f"Probate: {d['probate']}.",
        f"I claim the surplus funds listed at ${d['amount']} and held by {d['holder']} as the decedent's heir, "
        "for myself and for any other heirs according to their shares.",
    ]
    return _affidavit("Affidavit of heirship",
                      f"Before me, the undersigned authority, personally appeared {d['name']}, who being duly sworn "
                      "deposes and says:", statements, d, signature_png, signed_at, tz, cert_rows)


def agreement_pdf(text: str, signer: str, signature_png: bytes | None, signed_at: datetime, tz: str,
                  cert_rows: list[tuple[str, str]]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch, title="Agreement")
    story = [_p(line) if line.strip() else Spacer(1, 6) for line in text.splitlines()]
    story.append(Spacer(1, 12))
    if signature_png:
        sig = _sig_image(signature_png, 2.6 * inch, 0.7 * inch)
        if sig is not None:
            story.append(sig)
    story += [_p(f"Signed electronically by {signer}, {stamp(signed_at, tz)}")]
    doc.build(story)
    return _join(buf.getvalue(), _certificate_page(cert_rows))
