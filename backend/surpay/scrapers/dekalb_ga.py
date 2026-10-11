"""DeKalb County, GA — Tax Commissioner excess funds list (one PDF, spreadsheet export).

    15 093 11 101  $10,014.47  5/4/2021   JANE   Q   DOE   3284 HARVESTER WOODS ROAD  DECATUR  30034
    (parcel)       (excess)    (sale)     (first) (mid) (last) (situs address)        (city)   (zip)

Companies and estates are written whole in the first-name column ("ESTATE OF JOHN L DOE"), sometimes
with the surname repeated in the last-name column.
"""

import re
from datetime import date, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = "https://dekalbtaxga.gov/excess-funds/"
FALLBACK_URL = "https://dekalbtaxga.gov/wp-content/uploads/Excess-Funds-List.pdf"

# x positions (points), measured on a reference file where the header word
# "PARCEL" starts at x=33; anchored_bounds() shifts them to match each new file.
# Positions on the 1008pt-wide (legal landscape) page.
BOUNDS = {
    "parcel": (0, 84), "amount": (84, 155), "sale": (155, 205), "first": (205, 505),
    "middle": (505, 600), "last": (600, 705), "situs": (705, 840), "city": (840, 940), "zip": (940, 9999),
}
_PARCEL_RE = re.compile(r"^\d{2} \d{3} \d{2} \d{3}$")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "excess" in href and "list" in href and href.endswith(".pdf"):
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the excess funds list link on the DeKalb page")


def _owner(first: str, middle: str, last: str) -> str:
    if not last or last in first.split():
        return first  # business, estate or a name already written out in full
    return " ".join(p for p in (first, middle, last) if p)


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="PARCEL", expected_x=33)
    out = []
    for row in rows:
        c = columns(row, bounds)
        amount = c["amount"].replace("$", "")
        if not _PARCEL_RE.match(c["parcel"]) or not re.fullmatch(r"[\d,]+\.\d{2}", amount):
            continue
        sale: date | None = datetime.strptime(c["sale"], "%m/%d/%Y").date() if _DATE_RE.match(c["sale"]) else None
        address = ", ".join(p for p in (c["situs"], c["city"]) if p)
        out.append(RecordIn(
            source_key=f"{c['parcel']}|{sale.isoformat() if sale else c['sale']}",
            state="GA", county="DeKalb", sale_type="tax_sale",
            reference=f"Parcel {c['parcel']}",
            owner_name=_owner(c["first"], c["middle"], c["last"]),
            owner_address=f"{address}, GA {c['zip']}".strip() if address else "",
            amount_cents=parse_money(amount),
            sale_date=sale,
            source_url=source_url,
            raw=c,
        ))
    return out


class DeKalbCountyGA(Source):
    name = "dekalb_ga"
    state = "GA"
    county = "DeKalb"
    sale_type = "tax_sale"
    description = "DeKalb County, GA Tax Commissioner — excess funds from tax sales (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            try:
                page = client.get(PAGE_URL)
                page.raise_for_status()
                url = find_list_url(page.text)
            except (httpx.HTTPError, ValueError):
                url = FALLBACK_URL
            r = client.get(url)
            r.raise_for_status()
        return parse_rows(pdf_word_rows(r.content), url)
