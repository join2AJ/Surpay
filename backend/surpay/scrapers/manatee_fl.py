"""Manatee County, FL — Clerk's "List of Unclaimed Funds" from tax deed sales (HTML table).

    Case Number | Sale Date | Property Owner | Surplus Funds | 1 Year from Sale Date
    2025TD000103  9/15/2025   Jane Example     $98,991.49      9/15/2026

The table has empty spacer columns between the named ones, so cells are matched to the header
by position and the spacers are ignored.
"""

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money

PAGE_URL = "https://www.manateeclerk.com/departments/tax-deeds/list-of-unclaimed-funds"

_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_MONEY_RE = re.compile(r"^\$?\s*[\d,]+(\.\d{2})?$")


def _d(s: str) -> date | None:
    return datetime.strptime(s, "%m/%d/%Y").date() if _DATE_RE.match(s) else None


def _header_key(text: str) -> str | None:
    t = text.lower()
    for key, word in (("deadline", "year"), ("case", "case"), ("sale", "sale date"), ("owner", "owner"),
                      ("amount", "surplus")):
        if word in t:
            return key
    return None


def parse_html(page_html: str, source_url: str = PAGE_URL) -> list[RecordIn]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[RecordIn] = []
    for table in soup.find_all("table"):
        cols: dict[str, int] = {}
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if not cols:
                cols = {k: i for i, c in enumerate(cells) if (k := _header_key(c))}
                if not {"case", "owner", "amount"} <= cols.keys():
                    cols = {}
                    break
                continue
            get = lambda k: cells[cols[k]] if k in cols and cols[k] < len(cells) else ""  # noqa: E731
            case, owner, amount = get("case"), re.sub(r"\s+", " ", get("owner")), get("amount")
            if not re.fullmatch(r"\d{4}TD\d+", case) or not owner or not _MONEY_RE.match(amount):
                continue
            out.append(RecordIn(
                source_key=case,
                state="FL", county="Manatee", sale_type="tax_sale",
                reference=f"Case {case}",
                owner_name=owner,
                owner_address="",
                amount_cents=parse_money(amount.replace(" ", "")),
                sale_date=_d(get("sale")),
                source_url=source_url,
                raw={"case": case, "sale_date": get("sale"), "owner": owner, "amount": amount,
                     "one_year_from_sale": get("deadline")},
            ))
    return out


class ManateeCountyFL(Source):
    name = "manatee_fl"
    state = "FL"
    county = "Manatee"
    sale_type = "tax_sale"
    description = "Manatee County, FL Clerk of the Circuit Court — unclaimed tax deed surplus funds (web page)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(PAGE_URL)
            r.raise_for_status()
        recs = parse_html(r.text, PAGE_URL)
        if not recs and "Case Number" not in r.text:
            raise RuntimeError("Manatee County unclaimed funds table not found; the page layout may have changed")
        return recs
