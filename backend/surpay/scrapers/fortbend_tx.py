"""Fort Bend County, TX — District Clerk list of excess proceeds from tax sale (one PDF).

Each entry starts with a receipt date and case number; the case style (who was sued) and the
comment wrap onto the following lines:

    11/3/2009  07-DCV-156513  Fort Bend County, Et Al   $388.54  Payor   Court   Comment...
                              Vs.
                              Jane Q. Doe
"""

import re
from datetime import datetime

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, owner_from_style, parse_money, pdf_word_rows

URL = "https://odysseyreport.fortbendcountytx.gov/District_Clerk/ExcessProceedsFromTaxSale.pdf"

# x positions (points), measured on a reference file where the header word
# "Receipt" starts at x=70; anchored_bounds() shifts them to match each new file.
# Positions on the 963pt-wide landscape page.
BOUNDS = {
    "received": (0, 130), "case": (130, 215), "style": (215, 430), "amount": (430, 475),
    "payor": (475, 580), "court": (580, 705), "comment": (705, 9999),
}
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_CASE_RE = re.compile(r"^\d{2}-[A-Z]+-\d+$")
_MONEY_RE = re.compile(r"^\$[\d,]+\.\d{2}$")


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="Receipt", expected_x=70)
    entries: list[dict] = []
    for row in rows:
        # Amounts are right-aligned, so big ones start inside the style column: pick the
        # first dollar figure out by pattern rather than by position.
        money = next((t for _, t in row if _MONEY_RE.match(t)), None)
        if money:
            row = [(x, t) for x, t in row if t != money]
        c = columns(row, bounds)
        c["amount"] = money or ""
        if _DATE_RE.match(c["received"]) and _CASE_RE.match(c["case"]):
            entries.append({k: [v] for k, v in c.items()})
        elif entries and not c["received"] and not c["case"]:
            for k, v in c.items():
                if k != "amount":
                    entries[-1][k].append(v)

    out = []
    for e in entries:
        j = {k: " ".join(x for x in v if x) for k, v in e.items()}
        amount = j["amount"].split(" ")[0].replace("$", "")
        # The list also carries plain tax overpayment refunds; we only want sale surplus.
        if "excess" not in j["comment"].lower() or not re.fullmatch(r"[\d,]+\.\d{2}", amount):
            continue
        case, received = e["case"][0], e["received"][0]
        out.append(RecordIn(
            source_key=f"{case}|{received}|{amount}",
            state="TX", county="Fort Bend", sale_type="tax_sale",
            reference=f"Case {case}",
            owner_name=owner_from_style(j["style"]),
            owner_address="",
            amount_cents=parse_money(amount),
            sale_date=None,
            source_url=source_url,
            raw={**j, "received": datetime.strptime(received, "%m/%d/%Y").date().isoformat()},
        ))
    return out


class FortBendCountyTX(Source):
    name = "fortbend_tx"
    state = "TX"
    county = "Fort Bend"
    description = "Fort Bend County, TX District Clerk — excess proceeds from tax sale (PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            r = client.get(URL)
            r.raise_for_status()
        return parse_rows(pdf_word_rows(r.content), URL)
