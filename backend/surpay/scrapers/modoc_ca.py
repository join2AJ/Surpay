"""Modoc County, CA — Tax Collector's "Notice of Right to Claim Excess Proceeds" (R&T Code § 4676).

After each tax-defaulted property sale the Tax Collector publishes a notice listing every parcel
with excess proceeds, the date the tax deed was recorded, the parties of interest and the amount:

    Parcel #          Date of Deed   Parties of Interest                Amount
    002-075-006-000   06/02/26       DOE JOHN & ROE MARY (ESTATE)       12,797.28
                                     Mary Roe                               <- more parties of interest
    024-033-007-000;  06/02/26       EXAMPLE KENNETH W                   2,173.70
    024-033-008-000                                                         <- more parcels, same sale
                                                                76,332.19   <- total

The first party on the parcel line is the assessee (the former owner). Claims are only accepted
for one year after the deed is recorded (R&T Code § 4675), so expired notices are skipped.

The Tax Sales page only links some years' notices (the 2026 notice is reachable only by its
document number), so we combine links found on the page with the known notice addresses below.
"""

import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money, pdf_lines

PAGE_URL = "https://www.countyofmodoc.gov/629/Tax-Sales"
KNOWN_NOTICES = [
    "https://www.countyofmodoc.gov/DocumentCenter/View/1440/"
    "Notice-of-Right-to-Claim-Excess-Proceeds-from-the-Sale-of-Tax-Defaulted-Property-Published-June-25-July-2-and-9-2026",
]

_PARCEL = r"\d{3}-\d{3}-\d{3}-\d{3}"
_DEED = r"\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]+\.? \d{1,2}, \d{4}"
_ENTRY_RE = re.compile(rf"^\s*({_PARCEL})\s*[;&,]?\s+({_DEED})\s+(.+?)\s+([\d,]+\.\d{{2}})\s*$")
_MORE_PARCEL_RE = re.compile(rf"^\s*[;&,]?\s*({_PARCEL})\s*[;&,]?\s*$")
_TOTAL_RE = re.compile(r"^\s*([\d,]+\.\d{2})\s*$")
_SALE_RE = re.compile(r"sale of tax-defaulted property on\s+([A-Z][a-z]+)\s+(\d{1,2})(?:\s*-\s*\d{1,2})?,\s*(\d{4})", re.I)
_END_RE = re.compile(r"I certify or declare|penalty of perjury", re.I)


def find_notice_urls(page_html: str, base_url: str = PAGE_URL) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        text = (a["href"] + " " + a.get_text(" ")).lower()
        if "documentcenter/view" in text and "excess" in text and "proceeds" in text:
            url = urljoin(base_url, a["href"])
            if url not in urls:
                urls.append(url)
    return urls


def _deed_date(s: str) -> date:
    s = s.replace(".", "")
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognised deed date {s!r}")


def parse_lines(lines: list[str], source_url: str, today: date | None = None) -> list[RecordIn]:
    """Parse one notice. Parcels whose deed was recorded more than a year before `today`
    can no longer be claimed and are left out (pass today=None to keep everything)."""
    text = " ".join(lines)
    m = _SALE_RE.search(re.sub(r"\s+", " ", text))
    sale = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date() if m else None

    entries: list[dict] = []
    total = None
    started = False
    for line in lines:
        if not line.strip():
            continue
        if _END_RE.search(line):
            break
        if e := _ENTRY_RE.match(line):
            started = True
            entries.append({"parcels": [e.group(1)], "deed": _deed_date(e.group(2)),
                            "assessee": re.sub(r"\s+", " ", e.group(3)).strip(),
                            "amount": parse_money(e.group(4)), "others": []})
            continue
        if not started or not entries:
            continue
        if p := _MORE_PARCEL_RE.match(line):
            entries[-1]["parcels"].append(p.group(1))
        elif t := _TOTAL_RE.match(line):
            total = parse_money(t.group(1))
        elif not re.fullmatch(r"\s*\d{1,2}\s*", line):  # page number
            entries[-1]["others"].append(re.sub(r"\s+", " ", line).strip())

    if total is not None and sum(e["amount"] for e in entries) != total:
        raise ValueError("Modoc County excess proceeds do not add up to the notice total; "
                         "the layout may have changed")
    out = []
    for e in entries:
        deadline = e["deed"].replace(year=e["deed"].year + 1) if not (e["deed"].month == 2 and e["deed"].day == 29) \
            else date(e["deed"].year + 1, 3, 1)
        if today is not None and deadline < today:
            continue
        parcels = e["parcels"]
        out.append(RecordIn(
            source_key=f"{parcels[0]}|{e['deed'].isoformat()}",
            state="CA", county="Modoc", sale_type="tax_sale",
            reference="APN " + ", ".join(parcels),
            owner_name=e["assessee"],
            owner_address="",
            amount_cents=e["amount"],
            sale_date=sale,
            source_url=source_url,
            raw={"parcels": parcels, "deed_recorded": e["deed"].isoformat(), "claim_deadline": deadline.isoformat(),
                 "other_parties_of_interest": e["others"]},
        ))
    return out


class ModocCountyCA(Source):
    name = "modoc_ca"
    state = "CA"
    county = "Modoc"
    sale_type = "tax_sale"
    description = "Modoc County, CA Tax Collector — excess proceeds from tax-defaulted property sales (PDF notice)"

    def fetch(self) -> list[RecordIn]:
        records: dict[str, RecordIn] = {}
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            urls = find_notice_urls(page.text)
            urls += [u for u in KNOWN_NOTICES if u not in urls]
            for url in urls:
                r = client.get(url)
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                if r.content[:4] != b"%PDF":
                    raise RuntimeError(f"Modoc County notice {url} did not return a PDF")
                for rec in parse_lines(pdf_lines(r.content), url, today=date.today()):
                    records[rec.source_key] = rec
        return list(records.values())
