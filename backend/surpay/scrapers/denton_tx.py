"""Denton County, TX — District Clerk list of excess tax funds (one PDF, one page).

    23-0495-393  Doe, Jane S & Roe, John J     $220,537.18  4/7/2026
    (cause no.)  (defendant / former owner)    (amount)     (excess fund deposit date)

Some names are longer than their cell and overprint the amount column, so the page is read as one
stream of words in content order (cause, name..., amount, date) instead of by column position.
The county keeps the same DocumentCenter id when it replaces the file.
"""

import io
import re
from datetime import datetime

from .base import RecordIn, Source, http_client, parse_money

URL = "https://www.dentoncounty.gov/DocumentCenter/View/3044/Excess-Tax-Funds-PDF"

_CAUSE_RE = re.compile(r"^\d{2,4}-\d{2,6}-\d{1,3}$")
_MONEY_RE = re.compile(r"^\$[\d,]+\.\d{2}$")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def pdf_stream_words(content: bytes) -> list[str]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return [w["text"] for page in pdf.pages for w in page.extract_words(x_tolerance=1.5, use_text_flow=True)]


def parse_words(words: list[str], source_url: str) -> list[RecordIn]:
    out = []
    i = 0
    while i < len(words):
        if not _CAUSE_RE.match(words[i]):
            i += 1
            continue
        cause, j, name = words[i], i + 1, []
        while j < len(words) and not _MONEY_RE.match(words[j]) and not _CAUSE_RE.match(words[j]):
            name.append(words[j])
            j += 1
        if j + 1 >= len(words) or not _MONEY_RE.match(words[j]) or not _DATE_RE.match(words[j + 1]) or not name:
            i = j
            continue
        amount, deposited = words[j], datetime.strptime(words[j + 1], "%m/%d/%Y").date()
        owner = re.sub(r",?\s*\bEt\.?\s*Al\.?$", "", " ".join(name), flags=re.I)
        owner = re.sub(r"\s*-?\s*\(In Rem Only\)$", "", owner, flags=re.I).strip(" ,-")
        out.append(RecordIn(
            source_key=f"{cause}|{deposited.isoformat()}",
            state="TX", county="Denton", sale_type="tax_sale",
            reference=f"Cause {cause}",
            owner_name=owner,
            owner_address="",
            amount_cents=parse_money(amount),
            sale_date=None,  # the list gives the deposit date, not the sale date
            source_url=source_url,
            raw={"cause": cause, "name": " ".join(name), "amount": amount, "deposited": deposited.isoformat()},
        ))
        i = j + 2
    return out


class DentonCountyTX(Source):
    name = "denton_tx"
    state = "TX"
    county = "Denton"
    sale_type = "tax_sale"
    description = "Denton County, TX District Clerk — excess funds from tax sales (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(URL)
            r.raise_for_status()
        if r.content[:4] != b"%PDF":
            raise RuntimeError("Denton County excess tax funds link did not return a PDF")
        return parse_words(pdf_stream_words(r.content), URL)
