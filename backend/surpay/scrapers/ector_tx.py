"""Ector County, TX — District Clerk registry report of tax-sale excess proceeds (one PDF).

An Odyssey "Registry Accounts with Expected Disbursement Dates" report, grouped by court:

    C-20-212-T   Tax - Excess Proceeds  Doe, Jane Q        2/1/2024    22,689.80
    (case no.)   (registry account type) (on behalf of)    (expected disbursement) (current balance)

The expected disbursement date is when unclaimed funds go to the taxing units, i.e. the claim deadline.
"""

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money, pdf_lines

PAGE_URL = "https://www.ectorcountytx.gov/243/District-Clerk"

_LINE_RE = re.compile(
    r"^\s*(?P<case>\S+)\s+Tax\s*-\s*Excess Proceeds\s+(?P<name>.+?)\s+"
    r"(?P<disburse>\d{1,2}/\d{1,2}/\d{4})\s+(?P<amount>[\d,]+\.\d{2})\s*$"
)
_COURT_RE = re.compile(r"^\s*(\d+\w*\s+District Court|County Court at Law.*?)\s*$")


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        if "excess proceeds" in a.get_text(" ").lower():
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the excess proceeds link on the Ector County District Clerk page")


def parse_lines(lines: list[str], source_url: str) -> list[RecordIn]:
    out, court = [], ""
    for line in lines:
        cm = _COURT_RE.match(line)
        if cm:
            court = cm.group(1)
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        case = m["case"]
        name = re.sub(r"\s+,", ",", m["name"]).strip()
        disburse = datetime.strptime(m["disburse"], "%m/%d/%Y").date()
        out.append(RecordIn(
            source_key=f"{case}|{disburse.isoformat()}",  # the balance can change (interest); these don't
            state="TX", county="Ector", sale_type="tax_sale",
            reference=f"Case {case}",
            owner_name=name,
            owner_address="",
            amount_cents=parse_money(m["amount"]),
            sale_date=None,
            source_url=source_url,
            raw={"case": case, "name": name, "court": court, "amount": m["amount"],
                 "expected_disbursement": disburse.isoformat()},
        ))
    return out


class EctorCountyTX(Source):
    name = "ector_tx"
    state = "TX"
    county = "Ector"
    sale_type = "tax_sale"
    description = "Ector County, TX District Clerk — excess proceeds from tax sales held in the registry (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            r = client.get(url)
            r.raise_for_status()
        return parse_lines(pdf_lines(r.content), url)
