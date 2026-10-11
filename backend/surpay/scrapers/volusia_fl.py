"""Volusia County, FL — Clerk's tax deed surplus ledger (monthly PDF, Excel export, ~20 pages).

Published at a fixed URL that is overwritten each month. Columns:

    date surplus received | property owner name | cert # | amount of deposit | 3%/1.5% fee |
    balance after fee | refund per order | total amount paid | holds | remaining balance |
    date to remit to the State as unclaimed

Owner names that need several lines wrap upward: the cell is bottom-aligned, so the extra
name lines sit above the row that carries the date and the amounts.
"""

import re
from datetime import date, datetime

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = "https://www.clerk.org/tax-deeds.aspx"
LIST_URL = "https://www.clerk.org/pdf/user_publish/TaxDeeds/Tax_Deed_Surplus_List.pdf"

# x positions (points) on the 1224pt-wide page, measured on a reference file where the
# header word "CERT" starts at x=429; anchored_bounds() shifts them to match each new file.
BOUNDS = {
    "received": (0, 110), "owner": (110, 415), "cert": (415, 480), "deposit": (480, 575),
    "fee": (575, 660), "balance": (660, 730), "order": (730, 790), "paid": (790, 860),
    "holds": (860, 905), "remaining": (905, 1005), "remit": (1005, 9999),
}
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_CERT_RE = re.compile(r"^\d{1,6}-\d{2}$")
_MONEY_RE = re.compile(r"^[\d,]+\.\d{2}$")


def _d(s: str) -> date | None:
    return datetime.strptime(s, "%m/%d/%Y").date() if _DATE_RE.match(s) else None


def _money(s: str) -> str:
    return s.replace("$", "").replace(" ", "")


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="CERT", expected_x=429)
    owner_lo, owner_hi = bounds["owner"]
    out: list[RecordIn] = []
    seen: dict[str, int] = {}
    pending: list[str] = []  # wrapped owner-name lines waiting for their (bottom) row
    for row in rows:
        c = columns(row, bounds)
        if _DATE_RE.match(c["received"]) and _CERT_RE.match(c["cert"]):
            owner = " ".join(pending + [c["owner"]]).strip()
            pending = []
            remaining = _money(c["remaining"])
            if not _MONEY_RE.match(remaining) or parse_money(remaining) <= 0 or not owner:
                continue
            received = _d(c["received"])
            key = f"{c['cert']}|{received.isoformat() if received else ''}"
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:  # one certificate split between several owners on the same day
                key += f"#{seen[key]}"
            out.append(RecordIn(
                source_key=key,
                state="FL", county="Volusia", sale_type="tax_sale",
                reference=f"Tax Certificate {c['cert']}",
                owner_name=owner,
                owner_address="",
                amount_cents=parse_money(remaining),
                # The list gives the date the surplus was deposited (days after the sale), not the sale date.
                sale_date=received,
                source_url=source_url,
                raw={**c, "owner": owner, "deposit": _money(c["deposit"]), "remaining": remaining,
                     "remit_to_state": c["remit"]},
            ))
        elif row and all(owner_lo <= x < owner_hi for x, _ in row):
            pending.append(" ".join(t for _, t in row))
        else:
            pending = []  # page header, totals, footer: not part of any owner name
    return out


class VolusiaCountyFL(Source):
    name = "volusia_fl"
    state = "FL"
    county = "Volusia"
    sale_type = "tax_sale"
    description = "Volusia County, FL Clerk of the Circuit Court — tax deed surplus balances (monthly PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(LIST_URL)
            r.raise_for_status()
        if r.content[:4] != b"%PDF":
            raise RuntimeError("Volusia County tax deed surplus list did not return a PDF")
        return parse_rows(pdf_word_rows(r.content), LIST_URL)
