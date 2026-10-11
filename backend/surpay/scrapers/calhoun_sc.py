"""Calhoun County, SC — Tax Collector's tax sale overage lists (one PDF per sale year).

The Tax Collector page links one PDF per year ("Overages/CALHOUN-TaxColOvr_2023.pdf"); a new
one appears after each November sale, so we collect every overage link on each run. Lines:

    TAX SALE DATE: NOVEMBER 13, 2023                (only in some years)
    Sale#      Taxpayer                 Map#             Overage
    202300005  Doe, John Jr.            167-00-00-039    $  982.02

Under S.C. Code § 12-51-130 the overage belongs to the owner of record immediately before the
end of the redemption period and escheats to the county after five years.
"""

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import RecordIn, Source, http_client, parse_money, pdf_lines

PAGE_URL = "https://calhouncounty.sc.gov/departments/tax-collector"

_LINE_RE = re.compile(r"^\s*(\d{9})\s+(.+?)\s+(\d{3}-[\d.\-]+)\s+\$\s*([\d,]+\.\d{2})\s*$")
_SALE_DATE_RE = re.compile(r"TAX SALE DATE:\s*([A-Z]+ \d{1,2}, \d{4})", re.I)
# Some years were typed with Unicode hyphens (U+2010/2011/2013) in the map numbers.
_DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "−": "-"})


def find_list_urls(page_html: str, base_url: str = PAGE_URL) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/overages/" in href.lower() and href.lower().endswith(".pdf"):
            url = urljoin(base_url, href)
            if url not in urls:
                urls.append(url)
    if not urls:
        raise ValueError("Could not find any overage list links on the Calhoun County page")
    return urls


def parse_lines(lines: list[str], source_url: str) -> list[RecordIn]:
    sale_date = None
    out = []
    for raw_line in lines:
        line = raw_line.translate(_DASHES)
        if (d := _SALE_DATE_RE.search(line)) and sale_date is None:
            sale_date = datetime.strptime(d.group(1).title(), "%B %d, %Y").date()
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        sale_no, owner, map_no, amount = m.groups()
        out.append(RecordIn(
            source_key=sale_no,
            state="SC", county="Calhoun", sale_type="tax_sale",
            reference=f"Tax sale #{sale_no}, Map {map_no}",
            owner_name=re.sub(r"\s+", " ", owner).strip(),
            owner_address="",
            amount_cents=parse_money(amount),
            sale_date=sale_date,
            source_url=source_url,
            raw={"sale_number": sale_no, "map_number": map_no, "sale_year": int(sale_no[:4]),
                 "line": line.strip()},
        ))
    return out


class CalhounCountySC(Source):
    name = "calhoun_sc"
    state = "SC"
    county = "Calhoun"
    sale_type = "tax_sale"
    description = "Calhoun County, SC Tax Collector — tax sale overages, one PDF per sale year"

    def fetch(self) -> list[RecordIn]:
        records: list[RecordIn] = []
        with http_client() as client:
            page = client.get(PAGE_URL)
            page.raise_for_status()
            for url in find_list_urls(page.text):
                r = client.get(url)
                r.raise_for_status()
                if r.content[:4] != b"%PDF":
                    raise RuntimeError(f"Calhoun County overage list {url} did not return a PDF")
                records.extend(parse_lines(pdf_lines(r.content), url))
        return records
