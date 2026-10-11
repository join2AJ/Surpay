"""Wise County, TX — District Clerk excess proceeds report (monthly PDF, "TAX REGISTRY" accounts).

An Odyssey "Registry & Trust Accounts With Balances" report:

    TX13430   DOE, JANE E.     $15,392.41                 $15,392.41
    (case)    (party name)     (increases)  (decreases)   (net credit balance)

Party names are clipped at 40 characters by the report. A new file is posted each month
("AUGUST 2026 EXCESS PROCEEDS REPORT"), so the link is read from the Excess Proceeds page.
"""

import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money, pdf_lines

PAGE_URL = "https://www.co.wise.tx.us/453/Excess-Proceeds"

_MONEY = r"\$[\d,]+\.\d{2}"
_LINE_RE = re.compile(rf"^\s*(?P<case>TX\d+)\s+(?P<name>.+?)\s+(?P<moneys>{_MONEY}(?:\s+{_MONEY})*)\s*$")
_AS_OF_RE = re.compile(r"As of Date:\s*(\d{1,2}/\d{1,2}/\d{4})")


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        if "excess proceeds report" in a.get_text(" ").lower() and "documentcenter" in a["href"].lower():
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the excess proceeds report link on the Wise County page")


def parse_lines(lines: list[str], source_url: str) -> list[RecordIn]:
    as_of: date | None = None
    out = []
    for line in lines:
        am = _AS_OF_RE.search(line)
        if am:
            as_of = datetime.strptime(am.group(1), "%m/%d/%Y").date()
        m = _LINE_RE.match(line)
        if not m:
            continue
        balance = re.findall(_MONEY, m["moneys"])[-1]
        if parse_money(balance) <= 0:
            continue
        name = re.sub(r"\s+", " ", m["name"]).strip()
        out.append(RecordIn(
            source_key=m["case"],
            state="TX", county="Wise", sale_type="tax_sale",
            reference=f"Case {m['case']}",
            owner_name=name,
            owner_address="",
            amount_cents=parse_money(balance),
            sale_date=None,
            source_url=source_url,
            raw={"case": m["case"], "name": name, "balance": balance,
                 "as_of": as_of.isoformat() if as_of else None},
        ))
    return out


class WiseCountyTX(Source):
    name = "wise_tx"
    state = "TX"
    county = "Wise"
    sale_type = "tax_sale"
    description = "Wise County, TX District Clerk — excess proceeds from tax sales in the registry (monthly PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            r = client.get(url)
            r.raise_for_status()
        return parse_lines(pdf_lines(r.content), url)
