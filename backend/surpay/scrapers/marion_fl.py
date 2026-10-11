"""Marion County, FL — Clerk's "Tax Deeds Surplus Funds Report" (PDF, Excel export, ~20 pages).

The Clerk's Unclaimed Funds page links the current report, whose file name carries the run
date (Copy-of-Tax-Deeds-Surplus-Funds-2026-10-02.pdf), so we discover it on every run. Columns:

    Sale number | Tax number (certificate) | Parcel number | Current balance | Assessed_name

Long names wrap inside a vertically *centred* cell: a name of n lines puts as many lines above
the row that carries the numbers as below it (the middle line, if any, shares that row).
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = (
    "https://www.marioncountyclerk.org/departments/records-recording/"
    "tax-deeds-and-lands-available-for-taxes/unclaimed-funds/"
)

# x positions (points) on the 612pt page, measured on a reference file where the header word
# "Assessed_name" starts at x=348; anchored_bounds() shifts them to match each new file.
BOUNDS = {"sale": (0, 150), "cert": (150, 212), "parcel": (212, 278), "amount": (278, 340), "owner": (340, 9999)}
_SALE_RE = re.compile(r"^\d{5,7} ?[A-Z]?$")  # a resale gets a letter: "297006B"
_MONEY_RE = re.compile(r"^[\d,]+\.\d{2}$")


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "tax-deeds-surplus-funds" in href and href.endswith((".pdf", ".xlsx")):
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the tax deeds surplus funds report link on the Marion County page")


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="Assessed_name", expected_x=348)
    owner_lo = bounds["owner"][0]
    entries: list[dict] = []
    gap: list[str] = []  # name-only lines between two numbered rows
    above = 0  # how many name lines the previous entry took from above its row

    def settle_gap(next_entry: dict | None):
        """Split the name-only lines between the previous entry (below it) and the next (above it)."""
        nonlocal gap
        take = min(above, len(gap)) if entries else 0
        if take:
            entries[-1]["names"].extend(gap[:take])
        rest = gap[take:]
        if next_entry is not None:
            next_entry["names"][:0] = rest
        gap = []
        return len(rest)

    for row in rows:
        c = columns(row, bounds)
        amount = c["amount"].replace("$", "").replace(" ", "")
        if _SALE_RE.match(c["sale"]) and _MONEY_RE.match(amount):
            e = {**c, "sale": c["sale"].replace(" ", ""), "amount": amount, "names": [c["owner"]] if c["owner"] else []}
            above = settle_gap(e)
            entries.append(e)
        elif row and all(x >= owner_lo for x, _ in row):
            gap.append(" ".join(t for _, t in row))
        else:
            settle_gap(None)  # header / footer / total: close off the previous entry
            above = 0
    settle_gap(None)

    out: list[RecordIn] = []
    for e in entries:
        owner = " ".join(e["names"]).strip()
        if not owner or parse_money(e["amount"]) <= 0:
            continue
        out.append(RecordIn(
            source_key=e["sale"],
            state="FL", county="Marion", sale_type="tax_sale",
            reference=f"Tax Deed Sale {e['sale']}, Certificate {e['cert']}, Parcel {e['parcel']}",
            owner_name=owner,
            owner_address="",
            amount_cents=parse_money(e["amount"]),
            sale_date=None,  # the report does not give sale dates
            source_url=source_url,
            raw={k: v for k, v in e.items() if k != "names"} | {"owner": owner},
        ))
    return out


class MarionCountyFL(Source):
    name = "marion_fl"
    state = "FL"
    county = "Marion"
    sale_type = "tax_sale"
    description = "Marion County, FL Clerk of Court — tax deeds surplus funds report (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            r = client.get(url)
            r.raise_for_status()
        return parse_rows(pdf_word_rows(r.content), url)
