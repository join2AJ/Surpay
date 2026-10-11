"""Cuyahoga County, OH — Clerk of Courts excess funds spreadsheets.

The Clerk's "Excess Funds" page links Excel files on Azure blob storage whose `?sfvrsn=` suffix
changes on every update, so we discover the links on each run. Two lists are used:

* "Excess Funds - Foreclosure" — money left after sheriff's sales, still held by the Clerk:
      Case Number | Disp Date | Deposit | Bond | Plaintiff/Last.. | Defendant/Last | /First | /Middle | /Suffix
  The defendant is the former owner; the plaintiff (lender, tax-certificate holder) is kept in raw.
* "Excess Tax Foreclosure Funds released to Treasurer" — surplus from tax foreclosures the Clerk
  has paid over to the County Treasurer, who holds it for the former owner (ORC 5721.20):
      CASE NUMBER | CAPTION ("TREASURER OF CUYAHOGA COUNTY OHIO VS JANE DOE ET AL") | DATE | AMOUNT
  A case can appear on several rows (separate deposits); those are added together.

The "Non-Foreclosure" list (court deposits in ordinary civil cases) is not surplus and is skipped.
"""

import io
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client

PAGE_URL = "https://www.cuyahogacounty.gov/coc/excess-funds"

_VS_RE = re.compile(r"\s+vs\.?\s+", re.I)
_TRAILING_ETAL_RE = re.compile(r"[\s,]+(et\.?\s*al\.?|etal)\s*$", re.I)


def find_list_url(page_html: str, keyword: str, base_url: str = PAGE_URL) -> str:
    """keyword: 'excessfunds-foreclosure' or 'excesstaxforeclosurefunds'."""
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = href.lower().split("?", 1)[0]
        if keyword in path and path.endswith((".xlsx", ".xls")):
            return urljoin(base_url, href)
    raise ValueError(f"Could not find the {keyword!r} list link on the Cuyahoga County page")


def sheet_rows(content: bytes) -> list[tuple]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    return [row for ws in wb.worksheets for row in ws.iter_rows(values_only=True)]


def _cents(value) -> int:
    if value in (None, ""):
        return 0
    return round(float(str(value).replace("$", "").replace(",", "")) * 100)


def _date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    return None


def _s(value) -> str:
    return re.sub(r"\s+", " ", str(value)).strip() if value not in (None, "") else ""


def _header_index(rows: list[tuple], first_cell: str) -> int:
    for i, row in enumerate(rows):
        if row and _s(row[0]).lower() == first_cell:
            return i
    raise ValueError(f"Header {first_cell!r} not found; the list layout may have changed")


def parse_foreclosure_rows(rows: list[tuple], source_url: str) -> list[RecordIn]:
    h = _header_index(rows, "case number")
    cols = {_s(c).lower(): i for i, c in enumerate(rows[h]) if c}
    need = ["case number", "disp date", "deposit", "bond", "plaintiff/last", "defendant/last"]
    if missing := [c for c in need if c not in cols]:
        raise ValueError(f"Columns {missing} missing; the list layout may have changed")

    def get(row, name):
        i = cols.get(name)
        return row[i] if i is not None and i < len(row) else None

    out = []
    for row in rows[h + 1:]:
        case = _s(get(row, "case number"))
        amount = _cents(get(row, "deposit")) + _cents(get(row, "bond"))
        if not case or amount <= 0:
            continue
        last = _s(get(row, "defendant/last"))
        given = " ".join(p for p in (_s(get(row, "defendant/first")), _s(get(row, "defendant/middle"))) if p)
        owner = " ".join(p for p in (given, last, _s(get(row, "defendant/suffix"))) if p)
        plaintiff = " ".join(p for p in (_s(get(row, "plaintiff/first")), _s(get(row, "plaintiff/middle")),
                                         _s(get(row, "plaintiff/last"))) if p)
        disp = _date(get(row, "disp date"))
        out.append(RecordIn(
            source_key=case,
            state="OH", county="Cuyahoga", sale_type="mortgage_foreclosure",
            reference=f"Case {case}",
            owner_name=owner,
            owner_address="",
            amount_cents=amount,
            sale_date=disp,  # disposition date of the deposit; the list has no separate sale date
            source_url=source_url,
            raw={"case": case, "disp_date": disp.isoformat() if disp else None, "plaintiff": plaintiff,
                 "deposit_cents": _cents(get(row, "deposit")), "bond_cents": _cents(get(row, "bond"))},
        ))
    return out


def defendant(caption: str) -> str:
    parts = _VS_RE.split(caption, maxsplit=1)
    who = parts[1] if len(parts) == 2 else parts[0]
    return _TRAILING_ETAL_RE.sub("", who).strip(" ,.")


def parse_released_rows(rows: list[tuple], source_url: str) -> list[RecordIn]:
    h = _header_index(rows, "case number")
    cases: dict[str, dict] = {}
    for row in rows[h + 1:]:
        if not row or len(row) < 4:
            continue
        case, caption, when, amount = _s(row[0]), _s(row[1]), _date(row[2]), _cents(row[3])
        if not case or amount <= 0:
            continue
        c = cases.setdefault(case, {"caption": caption, "dates": [], "amounts": []})
        c["dates"].append(when)
        c["amounts"].append(amount)
    out = []
    for case, c in cases.items():
        dates = [d for d in c["dates"] if d]
        released = max(dates) if dates else None
        out.append(RecordIn(
            source_key=case,
            state="OH", county="Cuyahoga", sale_type="tax_sale",
            reference=f"Case {case}",
            owner_name=defendant(c["caption"]),
            owner_address="",
            amount_cents=sum(c["amounts"]),
            sale_date=released,  # date released to the Treasurer; the list has no sale date
            source_url=source_url,
            raw={"case": case, "caption": c["caption"], "released_to_treasurer": released.isoformat()
                 if released else None, "deposits_cents": c["amounts"]},
        ))
    return out


class CuyahogaCountyOH(Source):
    name = "cuyahoga_oh"
    state = "OH"
    county = "Cuyahoga"
    sale_type = "mortgage_foreclosure"
    description = "Cuyahoga County, OH Clerk of Courts — excess funds from foreclosure sales (Excel)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text, "excessfunds-foreclosure")
            r = client.get(url)
            r.raise_for_status()
        return parse_foreclosure_rows(sheet_rows(r.content), url)


class CuyahogaTreasurerOH(Source):
    name = "cuyahoga_tax_oh"
    state = "OH"
    county = "Cuyahoga"
    sale_type = "tax_sale"
    description = ("Cuyahoga County, OH — tax foreclosure surplus released by the Clerk of Courts to the "
                   "County Treasurer (Excel)")

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text, "excesstaxforeclosurefunds")
            r = client.get(url)
            r.raise_for_status()
        return parse_released_rows(sheet_rows(r.content), url)
