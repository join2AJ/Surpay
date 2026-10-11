"""Chatham County, GA — Tax Commissioner excess funds report (one PDF, refreshed monthly).

Each entry starts on a line with the PIN; the file name and bidder wrap, and the sale date and
remaining balance sit on the entry's last line:

    10046 03008  DOE JANE Q                                     JOHN BIDDER
                                                    5/4/2021    JR              $18,265.70
    10115 01059  IN REM AGAINST THE PROPERTY KNOWN AS LOT 1 ... SAID   ANOTHER BIDDER
                 PROPERTY BEING FORMERLY IN THE NAME OF ROE JOHN, DECEASED   1/2/2024   $1,884.08

For in-rem cases the former owner is the name after "FORMERLY IN THE NAME OF".
The report's link is an opaque CMS asset id, so it is read from the excess funds page.
"""

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Row, Source, anchored_bounds, columns, http_client, parse_money, pdf_word_rows

PAGE_URL = "https://tax.chathamcountyga.gov/ExcessFunds"

# x positions (points), measured on a reference file where the header word
# "Bidder" starts at x=615; anchored_bounds() shifts them to match each new file.
# Positions on the 792pt-wide landscape page.
BOUNDS = {"pin": (0, 95), "name": (95, 530), "sale": (530, 580), "bidder": (580, 680), "amount": (680, 9999)}
_PIN_RE = re.compile(r"^\d{5}[A-Z]?\s?\d{5}[A-Z]?\**$")
_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_PAGE_TEXT_RE = re.compile(r"OFFICE OF THE TAX COMMISSIONER|, Tax Commissioner$|^Excess Funds as of|^Updated \d")
_MONEY_RE = re.compile(r"^\$[\d,]+\.\d{2}$")
# Typed by hand, so tolerate "FORMERYL", "NAME COASTAL ..." (no OF) and "NAME OFJENKINS".
_FORMER_RE = re.compile(r"\bFORMER\w*\s+IN\s+THE\s+NAME\s*(?:OF)?\s*(.+)$", re.I)


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ").lower()
        if "excess funds report" in text and "form" not in text:
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the excess funds report link on the Chatham page")


def owner_from_file_name(name: str) -> str:
    m = _FORMER_RE.search(name)
    if m:
        name = m.group(1)
    name = re.sub(r"^IN REM\s+", "", name, flags=re.I)
    name = re.sub(r",?\s*DECEASED\b.*$", "", name, flags=re.I)
    return name.replace("*", "").strip(" ,.")


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    bounds = anchored_bounds(rows, BOUNDS, anchor="Bidder", expected_x=615)
    entries: list[dict[str, list[str]]] = []
    for row in rows:
        c = columns(row, bounds)
        if _PIN_RE.match(c["pin"]):
            entries.append({k: [v] for k, v in c.items()})
        elif entries and not c["pin"] and any(c.values()):
            if _PAGE_TEXT_RE.search(" ".join(t for _, t in row)):
                continue  # page title / footer, which falls between an entry's wrapped lines
            for k, v in c.items():
                entries[-1][k].append(v)

    out = []
    for e in entries:
        j = {k: " ".join(x for x in v if x) for k, v in e.items()}
        amount = next((t for t in j["amount"].split() if _MONEY_RE.match(t)), None)
        sale_s = next((t for t in j["sale"].split() if _DATE_RE.match(t)), "")
        if amount is None:
            continue
        pin = j["pin"].replace("*", "").strip()
        sale = datetime.strptime(sale_s, "%m/%d/%Y").date() if sale_s else None
        out.append(RecordIn(
            source_key=f"{pin}|{sale.isoformat() if sale else ''}",
            state="GA", county="Chatham", sale_type="tax_sale",
            reference=f"PIN {pin}",
            owner_name=owner_from_file_name(j["name"]),
            owner_address="",
            amount_cents=parse_money(amount),
            sale_date=sale,
            source_url=source_url,
            raw=j,
        ))
    return out


class ChathamCountyGA(Source):
    name = "chatham_ga"
    state = "GA"
    county = "Chatham"
    sale_type = "tax_sale"
    description = "Chatham County, GA Tax Commissioner — excess funds from tax sales (monthly PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            url = find_list_url(page.text)
            r = client.get(url)
            r.raise_for_status()
        return parse_rows(pdf_word_rows(r.content), url)
