"""Collier County, FL — Clerk's "Tax Deed Sales Excess Proceeds" list (one PDF, Excel export).

The Clerk keeps the list in its Laserfiche WebLink repository under a fixed document id that
is overwritten in place whenever the list is refreshed (the "As of:" stamp in the header moves).
One row per tax deed application (TDA):

    09/23/2024  24094  [unclaimed $]  [claim pending $]  1/26/2025  1st claim ...  WILLIAM JACKSON  285 EXETER ST  BROOKLYN  NY 11235  41614200006  GOLDEN GATE ...
    (sale)      (TDA)  (one of the two amount columns)   (120 days) (claims)      (titleholder)    (address)      (city)    (st/zip)  (parcel)     (legal)

Further claims ("2nd claim by ...") wrap onto lines of their own under the claims column.
"""

import re
from datetime import date, datetime

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = "https://www.collierclerk.com/tax-deed-sales/tax-deed-surplus/"
LIST_URL = (
    "https://app.collierclerk.com/LFOfficialRecords/edoc/6476/"
    "Tax%20Deed%20Sales%20Excess%20Proceeds%20List.pdf?dbid=0&repo=OFFICIALRECORDSPROD"
)

# x positions (points) on the 792pt landscape page, measured on a reference file where the
# header word "TDA" starts at x=37; anchored_bounds() shifts them to match each new file.
BOUNDS = {
    "sale": (0, 38), "tda": (38, 54), "unclaimed": (54, 88), "pending": (88, 118), "due": (118, 160),
    "claims": (160, 262), "owner": (262, 386), "address": (386, 492), "city": (492, 539),
    "stzip": (539, 584), "parcel": (584, 612), "legal": (612, 9999),
}
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_MONEY_RE = re.compile(r"^[\d,]+\.\d{2}$")


def _d(s: str) -> date | None:
    return datetime.strptime(s, "%m/%d/%Y").date() if _DATE_RE.match(s) else None


def _money(s: str) -> str:
    return s.replace("$", "").replace(" ", "")


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="TDA", expected_x=37)
    out: list[RecordIn] = []
    for row in rows:
        c = columns(row, bounds)
        if not re.fullmatch(r"\d{4,6}", c["tda"]) or not _DATE_RE.match(c["sale"]):
            if out and c["claims"] and not c["tda"]:
                out[-1].raw["claims"].append(c["claims"])  # "2nd claim by ..." wrapped lines
            continue
        unclaimed, pending = _money(c["unclaimed"]), _money(c["pending"])
        amount = unclaimed if _MONEY_RE.match(unclaimed) else pending
        if not _MONEY_RE.match(amount) or not c["owner"]:
            continue
        sale = _d(c["sale"])
        address = ", ".join(p for p in (c["address"], c["city"], c["stzip"]) if p)
        out.append(RecordIn(
            source_key=c["tda"],
            state="FL", county="Collier", sale_type="tax_sale",
            reference=f"Tax Deed Application {c['tda']}" + (f", Parcel {c['parcel']}" if c["parcel"] else ""),
            owner_name=c["owner"],
            owner_address=address,
            amount_cents=parse_money(amount),
            sale_date=sale,
            source_url=source_url,
            raw={**c, "status": "unclaimed" if amount == unclaimed else "claim pending",
                 "claims": [c["claims"]] if c["claims"] else []},
        ))
    return out


class CollierCountyFL(Source):
    name = "collier_fl"
    state = "FL"
    county = "Collier"
    sale_type = "tax_sale"
    description = "Collier County, FL Clerk of the Circuit Court — tax deed sale excess proceeds (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(LIST_URL)
            r.raise_for_status()
        if r.content[:4] != b"%PDF":
            raise RuntimeError("Collier County excess proceeds list did not return a PDF")
        return parse_rows(pdf_word_rows(r.content), LIST_URL)
