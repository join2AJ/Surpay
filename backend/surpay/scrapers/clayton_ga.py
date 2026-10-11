"""Clayton County, GA — Tax Commissioner excess funds listing (one PDF, monthly).

    WILLIAMS, DEVON            05213 214013 A07   $   44,134.74   11/05/24
    (owner as on the tax bill) (parcel)               (excess)    (sale date)

Long owner names are not clipped: they run on over the parcel column, so the two texts overlap on
the page. They are still separate runs in the PDF's content stream, so rows are read in stream order
(owner first, then parcel) rather than left to right.
"""

import io
import re
from datetime import date, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import RecordIn, Row, Source, http_client, parse_money

PAGE_URL = "https://publicaccess.claytoncountyga.gov/forms/htmlframe.aspx?mode=content/home_commissioner.htm"
FALLBACK_URL = "https://publicaccess.claytoncountyga.gov/content/PDF/DQ759GA.pdf"

_PARCEL_START_RE = re.compile(r"^\d{5}[A-Z]?$")
_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{2}$")
_MONEY_RE = re.compile(r"^[\d,]+\.\d{2}$")
PARCEL_X = 330  # parcels start at x≈346; owner words left of this can never begin the parcel


def find_list_url(page_html: str, base_url: str = PAGE_URL) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    for a in soup.find_all("a", href=True):
        if re.search(r"DQ759GA\.pdf$", a["href"], re.I) or "excess funds list" in a.get_text(" ").lower():
            return urljoin(base_url, a["href"])
    raise ValueError("Could not find the excess funds listing link on the Clayton page")


def pdf_stream_rows(content: bytes, y_tolerance: float = 3.5) -> list[Row]:
    """Words grouped into visual rows, each row kept in content-stream order (not sorted by x)."""
    import pdfplumber

    rows: list[Row] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            words = list(enumerate(page.extract_words(x_tolerance=1.5, use_text_flow=True)))
            words.sort(key=lambda iw: (iw[1]["top"], iw[0]))
            groups: list[list[tuple[int, dict]]] = []
            last_top = None
            for i, w in words:
                if last_top is None or w["top"] - last_top > y_tolerance:
                    groups.append([])
                groups[-1].append((i, w))
                last_top = w["top"]
            rows.extend([(w["x0"], w["text"]) for _, w in sorted(g, key=lambda iw: iw[0])] for g in groups)
            page.close()  # free the page's parsed layout
    return rows


def parse_rows(rows: list[Row], source_url: str) -> list[RecordIn]:
    out = []
    for row in rows:
        row = [(x, t) for x, t in row if t != "$"]  # the "$" sits apart from the figure, in either order
        texts = [t for _, t in row]
        if len(texts) < 4 or not _DATE_RE.match(texts[-1]) or not _MONEY_RE.match(texts[-2]):
            continue
        body = texts[:-2]
        xs = [x for x, _ in row][: len(body)]
        start = next((i for i in range(1, len(body)) if xs[i] >= PARCEL_X and _PARCEL_START_RE.match(body[i])), None)
        if start is None:
            continue
        owner = re.sub(r"\s+", " ", " ".join(body[:start])).strip()
        parcel = " ".join(body[start:])
        sale: date = datetime.strptime(texts[-1], "%m/%d/%y").date()
        out.append(RecordIn(
            source_key=f"{parcel}|{sale.isoformat()}",
            state="GA", county="Clayton", sale_type="tax_sale",
            reference=f"Parcel {parcel}",
            owner_name=owner,
            owner_address="",
            amount_cents=parse_money(texts[-2]),
            sale_date=sale,
            source_url=source_url,
            raw={"owner": owner, "parcel": parcel, "amount": texts[-2], "sale": texts[-1]},
        ))
    return out


class ClaytonCountyGA(Source):
    name = "clayton_ga"
    state = "GA"
    county = "Clayton"
    sale_type = "tax_sale"
    description = "Clayton County, GA Tax Commissioner — excess funds from tax sales (monthly PDF)"

    def fetch(self) -> list[RecordIn]:
        with http_client() as client:
            try:
                page = client.get(PAGE_URL)
                page.raise_for_status()
                url = find_list_url(page.text)
            except (httpx.HTTPError, ValueError):
                url = FALLBACK_URL
            r = client.get(url)
            r.raise_for_status()
        return parse_rows(pdf_stream_rows(r.content), url)
