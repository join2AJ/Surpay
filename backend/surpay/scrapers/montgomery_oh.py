"""Montgomery County, OH — Clerk of Courts excess funds list (one PDF, refreshed monthly).

The PDF lives at a fixed address and is overwritten each month ("As of September 1, 2026").
Each entry is one line, with long captions wrapping onto the next line:

    2017 CV 00103 TAX EASE OHIO LLC vs UNKNOWN DOE UNKNOWN HEIRS ETAL OF JANE $5,515.30
               DOE
    ...
    Total: $6,914,435.23

Most cases are mortgage or tax-certificate foreclosures; the defendant (after "vs") is the
former owner. Funds are released on a motion to the Court of Common Pleas (ORC 2329.44).
"""

import re
from datetime import datetime

from .base import RecordIn, Source, http_client, parse_money, pdf_lines

LIST_URL = "https://www.montgomerycountyclerkoh.gov/Downloads/Excess-Funds.pdf"

_ENTRY_RE = re.compile(r"^\s*(\d{4} [A-Z]{2} \d{4,6})\s+(.+?)\s+(\$[\d,]+\.\d{2})\s*$")
_AS_OF_RE = re.compile(r"As of\s+([A-Z][a-z]+ \d{1,2}, \d{4})")
_TOTAL_RE = re.compile(r"^\s*Total:\s*(\$[\d,]+\.\d{2})")
_SKIP_RE = re.compile(r"^\s*(\d+|Montgomery County Clerk of Courts|Excess Funds|As of .*|Case Number\s+Caption.*)\s*$")
_VS_RE = re.compile(r"\s+vs\.?\s+", re.I)
_TRAILING_ETAL_RE = re.compile(r"[\s,]+(et\.?\s*al\.?|etal)\s*$", re.I)


def defendant(caption: str) -> str:
    """'BANK vs JANE DOE ET AL' -> 'JANE DOE'. Only a trailing ET AL is dropped, so
    'UNKNOWN HEIRS ETAL OF JANE DOE' keeps the decedent's name."""
    parts = _VS_RE.split(caption, maxsplit=1)
    who = parts[1] if len(parts) == 2 else parts[0]
    return _TRAILING_ETAL_RE.sub("", who).strip(" ,.")


def parse_lines(lines: list[str], source_url: str) -> list[RecordIn]:
    entries: list[dict] = []
    as_of = None
    total = None
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if (m := _AS_OF_RE.search(line)) and as_of is None:
            as_of = datetime.strptime(m.group(1), "%B %d, %Y").date()
        if m := _TOTAL_RE.match(line):
            total = parse_money(m.group(1))
            continue
        if m := _ENTRY_RE.match(line):
            entries.append({"case": m.group(1), "caption": m.group(2).strip(), "amount": m.group(3)})
            continue
        if _SKIP_RE.match(line) or not entries:
            continue
        entries[-1]["caption"] += " " + line.strip()  # wrapped caption

    records = []
    for e in entries:
        caption = re.sub(r"\s+", " ", e["caption"])
        records.append(RecordIn(
            source_key=e["case"],
            state="OH", county="Montgomery", sale_type="mortgage_foreclosure",
            reference=f"Case {e['case']}",
            owner_name=defendant(caption),
            owner_address="",
            amount_cents=parse_money(e["amount"]),
            sale_date=None,  # the list does not give sale dates
            source_url=source_url,
            raw={"case": e["case"], "caption": caption, "list_as_of": as_of.isoformat() if as_of else None},
        ))
    if total is not None and sum(r.amount_cents for r in records) != total:
        raise ValueError("Montgomery County excess funds rows do not add up to the list total; "
                         "the layout may have changed")
    return records


class MontgomeryCountyOH(Source):
    name = "montgomery_oh"
    state = "OH"
    county = "Montgomery"
    sale_type = "mortgage_foreclosure"
    description = "Montgomery County, OH Clerk of Courts — excess funds from foreclosure sales (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(LIST_URL)
            r.raise_for_status()
        if r.content[:4] != b"%PDF":
            raise RuntimeError("Montgomery County excess funds list did not return a PDF")
        return parse_lines(pdf_lines(r.content), LIST_URL)
