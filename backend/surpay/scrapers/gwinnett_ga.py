"""Gwinnett County, GA — Tax Commissioner excess funds list (one PDF, spreadsheet export).

    3  BUYER NAME LLC        R5018 019A     DOE JANE MRS      187 MAIN ST      $3,789.69   May 2021
   (row) (buyer)             (parcel)       (owner, LAST FIRST) (situs)        (excess)    (sale month)

Note: Gwinnett accepts claims only from the owner or the owner's attorney, not from
asset-recovery firms.
"""

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = "https://gwinnetttaxcommissioner.com/property-tax/tax-sale-excess-funds"

# x positions (points), measured on a reference file where the header word
# "PARCEL" starts at x=318; anchored_bounds() shifts them to match each new file.
# Positions on the 792pt-wide landscape page.
BOUNDS = {
    "row": (0, 46), "buyer": (46, 315), "parcel": (315, 368), "owner": (368, 590),
    "situs": (590, 715), "amount": (715, 750), "month": (750, 9999),
}


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "excess-funds" in href and "pdf" in href and "packet" not in href:
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the excess funds list link on the Gwinnett page")


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="PARCEL", expected_x=318)
    out = []
    for row in rows:
        c = columns(row, bounds)
        amount = c["amount"].replace("$", "")
        if not re.fullmatch(r"[\d,]+\.\d{2}", amount) or not c["parcel"] or not c["owner"]:
            continue
        try:
            sale = datetime.strptime(f"1 {c['month']}", "%d %B %Y").date()
        except ValueError:
            sale = None
        situs = c["situs"]
        out.append(RecordIn(
            source_key=f"{c['parcel']}|{sale.isoformat() if sale else ''}",
            state="GA", county="Gwinnett", sale_type="tax_sale",
            reference=f"Parcel {c['parcel']}",
            owner_name=c["owner"],
            owner_address=f"{situs}, Gwinnett County, GA" if situs else "",
            amount_cents=parse_money(amount),
            sale_date=sale,
            source_url=source_url,
            raw=c,
        ))
    return out


class GwinnettCountyGA(Source):
    name = "gwinnett_ga"
    state = "GA"
    county = "Gwinnett"
    description = "Gwinnett County, GA Tax Commissioner — excess funds from tax sales (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            r = client.get(url)
            r.raise_for_status()
        return parse_rows(pdf_word_rows(r.content), url)
