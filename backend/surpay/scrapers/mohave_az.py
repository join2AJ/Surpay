"""Mohave County, AZ — Treasurer's list of excess proceeds from trustee (deed of trust) sales.

When a trustee's sale brings more than the lender is owed, the trustee may deposit the balance
with the County Treasurer (A.R.S. § 33-812). The Treasurer's page shows them as an HTML table:

    Data provided as of 10/2/2026
    Case Number | Trustor          | Deposit Date | Deposit Amount | Current Balance
    2024-00033  | JANE Q. EXAMPLE  | 1/16/2024    | $133,730.19    | $133,730.19

The trustor is the former owner. "Current Balance" is what is still held (part may already have
been paid out), so that is the amount we list. Release is by application to the Superior Court.
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money

PAGE_URL = "https://www.mohave.gov/departments/treasurer/general-use/excess-proceeds-list/"

_AS_OF_RE = re.compile(r"as of\s+(\d{1,2}/\d{1,2}/\d{4})", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_page(html: str, source_url: str = PAGE_URL) -> list[RecordIn]:
    soup = BeautifulSoup(html, "html.parser")
    m = _AS_OF_RE.search(soup.get_text(" "))
    as_of = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat() if m else None
    for table in soup.find_all("table"):
        rows = [[_norm(c.get_text(" ")) for c in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
        if not rows:
            continue
        header = [h.lower() for h in rows[0]]
        if "case number" in header and "trustor" in header:
            break
    else:
        raise ValueError("Excess proceeds table not found; the Mohave County page layout may have changed")

    col = {h: i for i, h in enumerate(header)}
    bal_col = col.get("current balance", col.get("deposit amount"))
    out = []
    for row in rows[1:]:
        if len(row) < len(header):
            continue
        case, trustor, balance = row[col["case number"]], row[col["trustor"]], row[bal_col]
        if not re.fullmatch(r"\$?[\d,]+\.\d{2}", balance) or not case:
            continue
        cents = parse_money(balance)
        if cents <= 0:
            continue
        deposited = None
        if "deposit date" in col:
            try:
                deposited = datetime.strptime(row[col["deposit date"]], "%m/%d/%Y").date()
            except ValueError:
                pass
        deposit_amount = row[col["deposit amount"]] if "deposit amount" in col else ""
        out.append(RecordIn(
            source_key=case,
            state="AZ", county="Mohave", sale_type="mortgage_foreclosure",
            reference=f"Treasurer case {case}",
            owner_name=trustor,
            owner_address="",
            amount_cents=cents,
            sale_date=deposited,  # date deposited with the Treasurer, shortly after the trustee's sale
            source_url=source_url,
            raw={"case": case, "trustor": trustor, "deposit_date": row[col["deposit date"]] if "deposit date" in col
                 else None, "deposit_amount": deposit_amount, "current_balance": balance, "list_as_of": as_of},
        ))
    return out


class MohaveCountyAZ(Source):
    name = "mohave_az"
    state = "AZ"
    county = "Mohave"
    sale_type = "mortgage_foreclosure"
    description = "Mohave County, AZ Treasurer — excess proceeds from trustee's sales (A.R.S. 33-812)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(PAGE_URL)
            r.raise_for_status()
        return parse_page(r.text, PAGE_URL)
