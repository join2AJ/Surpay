"""Dallas County, TX — District Clerk excess funds list (tax suit sheriff sales).

Published monthly as ExcessFunds-MMDDYY.pdf, dated the 1st of the month. Columns:
case no. | style (County vs Owner) | source | excess amount | payment received | notice mailed |
date of sale | end of redemption period.
"""

import re
from datetime import date, datetime

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, owner_from_style, parse_money, pdf_word_rows

URL = "https://www.dallascounty.org/Assets/uploads/docs/district-clerk/excess-funds/ExcessFunds-{:%m%d%y}.pdf"

# x positions (points), measured on a reference file where the header word
# "CASE" starts at x=58; anchored_bounds() shifts them to match each new file.
# Positions of each column on the 612pt-wide page.
BOUNDS = {
    "case": (0, 80), "style": (80, 325), "source": (325, 365), "amount": (365, 420),
    "received": (420, 458), "mailed": (458, 485), "sale": (485, 515), "redemption": (515, 9999),
}
_CASE_RE = re.compile(r"^[A-Z]{2}-?[\d-]{5,}$")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def _d(s: str) -> date | None:
    return datetime.strptime(s, "%m/%d/%Y").date() if _DATE_RE.match(s) else None


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="CASE", expected_x=58)
    out = []
    for row in rows:
        c = columns(row, bounds)
        amount = c["amount"].replace("$", "").replace(" ", "")
        if not _CASE_RE.match(c["case"]) or not re.fullmatch(r"[\d,]+\.\d{2}", amount):
            continue
        out.append(RecordIn(
            source_key=f"{c['case']}|{amount}",
            state="TX", county="Dallas", sale_type="tax_sale",
            reference=f"Case {c['case']}",
            owner_name=owner_from_style(c["style"]),
            owner_address="",
            amount_cents=parse_money(amount),
            sale_date=_d(c["sale"]),
            source_url=source_url,
            raw={**c, "amount": amount},
        ))
    return out


def candidate_urls(today: date, months_back: int = 6) -> list[str]:
    urls, y, mo = [], today.year, today.month
    for _ in range(months_back + 1):
        urls.append(URL.format(date(y, mo, 1)))
        y, mo = (y, mo - 1) if mo > 1 else (y - 1, 12)
    return urls


class DallasCountyTX(Source):
    name = "dallas_tx"
    state = "TX"
    county = "Dallas"
    description = "Dallas County, TX District Clerk — excess funds from tax sales (monthly PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            for url in candidate_urls(date.today()):
                r = client.get(url)
                if r.status_code == 200 and r.content[:4] == b"%PDF":
                    return parse_rows(pdf_word_rows(r.content), url)
        raise RuntimeError("No Dallas County excess funds PDF found for the last 6 months")
