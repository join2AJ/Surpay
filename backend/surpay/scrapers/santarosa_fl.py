"""Santa Rosa County, FL — Clerk's "Tax Deed Surplus Money" list (one-page PDF, Excel export).

The Clerk's foreclosures & tax deeds page links the current file, whose name carries the
revision date (santa-rosa-county-tax-deed-surplus-rev-09-03-2026_ADA.pdf), so we discover it
on every run. Columns:

    FILE#     SURPLUS     SALE DATE  PAYEE                         ADDRESS            CITY    ST  ZIP
    2020192   $17,743.83  11/2/2020  CAPITOL INVESTMENT CO INC     C/O M MAX WILKS
                                                                   8050 BLACKWATER DR MILTON  FL  32583
    2024302   $95.72      5/12/2025  WAYNE C BROXSON               12183 DALE DR      MC CALLA AL 35111
                                     JACKIE BROXSON

Cells are top-aligned: a second line under a row continues its payee (co-owner) and/or address.
A file split between heirs appears once per payee, each with its own share.
"""

import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = "https://santarosaclerk.com/courts/foreclosures-tax-deeds/"

# x positions (points) on the 612pt page, measured on a reference file where the header word
# "PAYEE" starts at x=151; anchored_bounds() shifts them to match each new file.
BOUNDS = {
    "file": (0, 80), "money_date": (80, 149), "payee": (149, 268),
    "address": (268, 404), "city": (404, 480), "st": (480, 525), "zip": (525, 9999),
}
_FILE_RE = re.compile(r"^\d{7}$")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_MONEY_RE = re.compile(r"^[\d,]+\.\d{2}$")


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if "tax-deed-surplus" in href and href.endswith(".pdf") and "form" not in href:
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the tax deed surplus list link on the Santa Rosa page")


def _d(s: str) -> date | None:
    return datetime.strptime(s, "%m/%d/%Y").date() if _DATE_RE.match(s) else None


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="PAYEE", expected_x=151)
    entries: list[dict] = []
    for row in rows:
        c = columns(row, bounds)
        # Amount and sale date sit so close together that a long amount pushes the date across
        # any fixed boundary, so split that region by content instead of by position.
        parts = c.pop("money_date").split()
        c["sale"] = next((p for p in parts if _DATE_RE.match(p)), "")
        c["amount"] = "".join(p for p in parts if not _DATE_RE.match(p))
        amount = c["amount"].replace("$", "")
        if _FILE_RE.match(c["file"]) and _MONEY_RE.match(amount):
            entries.append({**c, "amount": amount, "payees": [c["payee"]], "addr_lines": [c["address"]]})
        elif entries and not c["file"] and not parts and (c["payee"] or c["address"]):
            e = entries[-1]  # continuation line of the row above
            if c["payee"]:
                e["payees"].append(c["payee"])
            if c["address"]:
                e["addr_lines"].append(c["address"])
            for k in ("city", "st", "zip"):
                e[k] = e[k] or c[k]
    out: list[RecordIn] = []
    seen: dict[str, int] = {}
    for e in entries:
        owner = " & ".join(p for p in e["payees"] if p)
        if not owner:
            continue
        sale = _d(e["sale"])
        key = f"{e['file']}|{owner}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key += f"#{seen[key]}"
        street = ", ".join(a for a in e["addr_lines"] if a)
        place = " ".join(p for p in (e["st"], e["zip"]) if p)
        address = ", ".join(p for p in (street, e["city"], place) if p)
        out.append(RecordIn(
            source_key=key,
            state="FL", county="Santa Rosa", sale_type="tax_sale",
            reference=f"Tax Deed File {e['file']}",
            owner_name=owner,
            owner_address=address,
            amount_cents=parse_money(e["amount"]),
            sale_date=sale,
            source_url=source_url,
            raw={k: v for k, v in e.items()},
        ))
    return out


class SantaRosaCountyFL(Source):
    name = "santarosa_fl"
    state = "FL"
    county = "Santa Rosa"
    sale_type = "tax_sale"
    description = "Santa Rosa County, FL Clerk of Court — tax deed surplus money list (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            r = client.get(url)
            r.raise_for_status()
        return parse_rows(pdf_word_rows(r.content), url)
