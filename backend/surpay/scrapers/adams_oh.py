"""Adams County, Ohio — Auditor's list of surplus funds from tax sales.

The auditor's "Surplus Funds" page links a Word (sometimes PDF) document that is replaced
when it is updated, so we discover the current link on every run. Entries look like:

    $4,686.31   Ed Example, 850 Some Lane, Peebles, OH 45660
    Date of Sale:  6/17/24   Payment received: 6/24/24   Parcel # 068-00-00-045.019
                                                         Parcel # 068-00-00-045.020
"""

import io
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money

PAGE_URL = "https://adamsoh-auditor.schneidergis.com/site-links/surplus-funds/"

_ENTRY_RE = re.compile(r"^\s*(\$[\d,]+\.\d{2})\s+(.+)$")
_SALE_RE = re.compile(r"Date of Sale\s*:\s*(\d{1,2}/\d{1,2}/\d{2,4})", re.I)
_PARCEL_RE = re.compile(r"Parcel\s*#\s*([\d.\-]+)", re.I)


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "surplus-funds-list" in href and href.endswith((".docx", ".pdf")):
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the surplus funds list link on the Adams County page")


def document_lines(content: bytes, url: str) -> list[str]:
    if url.lower().endswith(".pdf"):
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text(layout=True) or "" for page in pdf.pages)
        return text.splitlines()
    import docx

    return [p.text for p in docx.Document(io.BytesIO(content)).paragraphs]


def _parse_date(s: str) -> date:
    fmt = "%m/%d/%y" if len(s.rsplit("/", 1)[-1]) == 2 else "%m/%d/%Y"
    return datetime.strptime(s, fmt).date()


def parse_lines(lines: list[str], source_url: str) -> list[RecordIn]:
    records: list[RecordIn] = []
    current: dict | None = None

    def flush():
        if current and current["parcels"]:
            name, _, address = current["who"].partition(",")
            parcels = current["parcels"]
            sale = current["sale_date"]
            records.append(
                RecordIn(
                    source_key=f"{parcels[0]}|{sale.isoformat() if sale else ''}",
                    state="OH",
                    county="Adams",
                    sale_type="tax_sale",
                    reference="Parcel " + ", ".join(parcels),
                    owner_name=name.strip(),
                    owner_address=address.strip(),
                    amount_cents=current["amount"],
                    sale_date=sale,
                    source_url=source_url,
                    raw={"lines": current["lines"]},
                )
            )

    for line in lines:
        if not line.strip():
            continue
        m = _ENTRY_RE.match(line)
        if m:
            flush()
            current = {
                "amount": parse_money(m.group(1)),
                "who": re.sub(r"\s+", " ", m.group(2)).strip(),
                "sale_date": None,
                "parcels": [],
                "lines": [line.strip()],
            }
            continue
        if current is None:
            continue
        current["lines"].append(line.strip())
        if (s := _SALE_RE.search(line)) and current["sale_date"] is None:
            current["sale_date"] = _parse_date(s.group(1))
        current["parcels"].extend(_PARCEL_RE.findall(line))
    flush()
    return records


class AdamsCountyOH(Source):
    name = "adams_oh"
    state = "OH"
    county = "Adams"
    description = "Adams County, OH Auditor — surplus funds from tax sales"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            doc = client.get(url)
            doc.raise_for_status()
        return parse_lines(document_lines(doc.content, url), url)
