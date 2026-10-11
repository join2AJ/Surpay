"""Taylor County, FL — Clerk's "Tax Deeds Surplus" list (HTML table on the department page).

    TDA # | Owner's Name | Parcel Number | Certificate # | Amount | Sale Date | Note
    22-034  Jane Example   R05725-553      849 of 2019     $ 6,793.92  12/12/2022
"""

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money

PAGE_URL = "https://taylorclerk.com/departments/tax-deeds-surplus/"

_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_MONEY_RE = re.compile(r"^\$?[\d,]+(\.\d{2})?$")
_HEADERS = (("tda", "tda"), ("owner", "owner"), ("parcel", "parcel"), ("cert", "certificate"),
            ("amount", "amount"), ("sale", "sale date"), ("note", "note"))


def _d(s: str) -> date | None:
    return datetime.strptime(s, "%m/%d/%Y").date() if _DATE_RE.match(s) else None


def _header_key(text: str) -> str | None:
    t = text.lower()
    return next((k for k, word in _HEADERS if word in t), None)


def parse_html(page_html: str, source_url: str = PAGE_URL) -> list[RecordIn]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[RecordIn] = []
    for table in soup.find_all("table"):
        cols: dict[str, int] = {}
        for tr in table.find_all("tr"):
            cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            if not cols:
                cols = {k: i for i, c in enumerate(cells) if (k := _header_key(c))}
                if not {"tda", "owner", "amount"} <= cols.keys():
                    cols = {}
                    break
                continue
            c = {k: (cells[i] if i < len(cells) else "") for k, i in cols.items()}
            amount = c["amount"].replace(" ", "")
            if not re.fullmatch(r"\d{2}-\d{2,4}", c["tda"]) or not c["owner"] or not _MONEY_RE.match(amount):
                continue
            if parse_money(amount) <= 0:
                continue
            parcel = c.get("parcel", "")
            out.append(RecordIn(
                source_key=c["tda"],
                state="FL", county="Taylor", sale_type="tax_sale",
                reference=f"TDA {c['tda']}" + (f", Parcel {parcel}" if parcel else ""),
                owner_name=c["owner"],
                owner_address="",
                amount_cents=parse_money(amount),
                sale_date=_d(c.get("sale", "")),
                source_url=source_url,
                raw=c,
            ))
    return out


class TaylorCountyFL(Source):
    name = "taylor_fl"
    state = "FL"
    county = "Taylor"
    sale_type = "tax_sale"
    description = "Taylor County, FL Clerk of Court — tax deed surplus list (web page)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(PAGE_URL)
            r.raise_for_status()
        recs = parse_html(r.text, PAGE_URL)
        if not recs:
            raise RuntimeError("Taylor County tax deed surplus table not found; the page layout may have changed")
        return recs
