"""Cobb County, GA — Tax Commissioner excess funds list (one PDF, spreadsheet export, monthly).

    9/1/2020  BUYER LLC          DOE JANE Q          17-0297-0-086-0  $1,077.03  Yes
    (sale)    (purchaser)        (owner)             (parcel)         (excess)   (pending claim)

The file name changes every month ("...Excel Template Seal_October.pdf"), so the link is read from
the delinquent-taxes page. Cobb interpleads these funds into Superior Court over time.
"""

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = "https://www.cobbtax.gov/property/delinquent_taxes/index.php"

# x positions (points), measured on a reference file where the header word
# "Parcel" starts at x=485; anchored_bounds() shifts them to match each new file.
# Positions on the 792pt-wide landscape page.
BOUNDS = {
    "sale": (0, 98), "purchaser": (98, 280), "owner": (280, 480), "parcel": (480, 575),
    "amount": (575, 660), "pending": (660, 9999),
}
_PARCEL_RE = re.compile(r"(\d{2}-\d{4}-\d-\d{3}-\d)$")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    base = soup.find("base", href=True)
    if base:
        base_url = urljoin(base_url, base["href"])
    links = [a for a in soup.find_all("a", href=True) if "excess funds" in a["href"].lower()
             and a["href"].lower().split("?")[0].endswith(".pdf") and "packet" not in a["href"].lower()]
    # The body text link ("View Current Excess Funds List") is newer than the side-menu one.
    links.sort(key=lambda a: "current" not in a.get_text(" ").lower())
    if not links:
        raise ValueError("Could not find the excess funds list link on the Cobb page")
    return urljoin(base_url, links[0]["href"].replace(" ", "%20"))


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="Parcel", expected_x=485)
    out = []
    for row in rows:
        c = columns(row, bounds)
        amount = c["amount"].replace("$", "")
        # A long owner name runs into the parcel cell with no space ("...A/K/A HAS19-0928-0-074-0").
        owner_parcel = f"{c['owner']} {c['parcel']}".strip()
        m = _PARCEL_RE.search(owner_parcel)
        if not m or not re.fullmatch(r"[\d,]+\.\d{2}", amount):
            continue
        c["owner"], c["parcel"] = owner_parcel[: m.start()].strip(), m.group(1)
        sale = datetime.strptime(c["sale"], "%m/%d/%Y").date() if _DATE_RE.match(c["sale"]) else None
        out.append(RecordIn(
            source_key=f"{c['parcel']}|{sale.isoformat() if sale else c['sale']}",
            state="GA", county="Cobb", sale_type="tax_sale",
            reference=f"Parcel {c['parcel']}",
            owner_name=c["owner"],
            owner_address="",
            amount_cents=parse_money(amount),
            sale_date=sale,
            source_url=source_url,
            raw=c,
        ))
    return out


class CobbCountyGA(Source):
    name = "cobb_ga"
    state = "GA"
    county = "Cobb"
    sale_type = "tax_sale"
    description = "Cobb County, GA Tax Commissioner — excess funds from tax sales (monthly PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            r = client.get(url)
            r.raise_for_status()
        return parse_rows(pdf_word_rows(r.content), url)
