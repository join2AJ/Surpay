"""Forsyth County, GA — Tax Commissioner excess funds listing (an HTML table on its own page).

Columns: date sold | parcel ID | defendant in fi. fa. (the owner) | defendant's mailing address |
property address | purchase price | total amount due | excess funds.
"""

import re
import time
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money

PAGE_URL = "https://forsythcountytax.com/tax-sales-excess-funds/"
FALLBACK_LIST_URL = "https://forsythcountytax.com/excess-funds-listing-2/"

_MONEY_RE = re.compile(r"^\$?[\d,]+\.\d{2}$")


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        if "excess-funds-listing" in a["href"].lower():
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the excess funds listing link on the Forsyth page")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def parse_table(page_html: str, source_url: str) -> list[RecordIn]:
    soup = BeautifulSoup(page_html, "html.parser")
    table = next((t for t in soup.find_all("table") if "EXCESS FUNDS" in t.get_text(" ").upper()), None)
    if table is None:
        raise ValueError("Excess funds table not found; the Forsyth page layout may have changed")
    header: list[str] = []
    out = []
    for tr in table.find_all("tr"):
        cells = [_clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
        if not header:
            header = [h.upper() for h in cells]
            continue
        if len(cells) != len(header):
            continue
        c = dict(zip(header, cells))
        excess, parcel, owner = c.get("EXCESS FUNDS", ""), c.get("PARCEL ID", ""), c.get("DEFENDANT IN FIFA", "")
        if not _MONEY_RE.match(excess) or not parcel or not owner:
            continue
        try:
            sale = datetime.strptime(c.get("DATE SOLD", ""), "%m/%d/%Y").date()
        except ValueError:
            sale = None
        out.append(RecordIn(
            source_key=f"{parcel}|{sale.isoformat() if sale else c.get('DATE SOLD', '')}",
            state="GA", county="Forsyth", sale_type="tax_sale",
            reference=f"Parcel {parcel}",
            owner_name=owner,
            owner_address=c.get("DEFENDANT IN FIFA ADDRESS", ""),
            amount_cents=parse_money(excess),
            sale_date=sale,
            source_url=source_url,
            raw=c,
        ))
    return out


class ForsythCountyGA(Source):
    name = "forsyth_ga"
    state = "GA"
    county = "Forsyth"
    sale_type = "tax_sale"
    description = "Forsyth County, GA Tax Commissioner — excess funds from tax sales (web page table)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            try:
                page = client.get(PAGE_URL)
                page.raise_for_status()
                url = find_list_url(page.text)
            except (httpx.HTTPError, ValueError):
                url = FALLBACK_LIST_URL
            r = client.get(url)
            if r.status_code == 429:  # the site rate-limits back-to-back requests
                time.sleep(10)
                r = client.get(url)
            r.raise_for_status()
        return parse_table(r.text, url)
