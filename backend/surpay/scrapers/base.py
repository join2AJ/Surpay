import re
from dataclasses import dataclass, field
from datetime import date

import httpx

from .. import config


@dataclass
class RecordIn:
    source_key: str
    state: str
    county: str
    sale_type: str
    reference: str
    owner_name: str
    owner_address: str
    amount_cents: int
    sale_date: date | None
    source_url: str
    raw: dict = field(default_factory=dict)


class Source:
    """A publisher of surplus records. Subclasses implement fetch()."""

    name: str = ""
    state: str = ""
    county: str = ""
    description: str = ""

    def fetch(self) -> list[RecordIn]:
        raise NotImplementedError


def http_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": config.USER_AGENT},
        timeout=60,
        follow_redirects=True,
    )


def parse_money(text: str) -> int:
    """'$48,009.13' -> 4800913 (cents)."""
    cleaned = text.replace("$", "").replace(",", "").strip()
    whole, _, frac = cleaned.partition(".")
    return int(whole or 0) * 100 + int((frac + "00")[:2])


def pdf_lines(content: bytes) -> list[str]:
    """Text of a PDF with its column layout preserved, one string per line."""
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return [ln for page in pdf.pages for ln in (page.extract_text(layout=True) or "").splitlines()]


Row = list[tuple[float, str]]  # (x position, word) for one visual line of a PDF table


def pdf_word_rows(content: bytes, y_tolerance: float = 3.5) -> list[Row]:
    """Words of a PDF grouped into visual rows, left to right.

    Table PDFs exported from spreadsheets often place cells of one row a point or two apart
    vertically, so words whose tops are within `y_tolerance` of the previous word join its row.
    """
    import io

    import pdfplumber

    rows: list[Row] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            words = sorted(page.extract_words(x_tolerance=1.5), key=lambda w: (w["top"], w["x0"]))
            last_top = None
            for w in words:
                if last_top is None or w["top"] - last_top > y_tolerance:
                    rows.append([])
                rows[-1].append((w["x0"], w["text"]))
                last_top = w["top"]
    return [sorted(r) for r in rows]


def columns(row: Row, bounds: dict[str, tuple[float, float]]) -> dict[str, str]:
    """Split a row into named columns by x position: bounds = {"name": (x_from, x_to)}."""
    out = {name: [] for name in bounds}
    for x, text in row:
        for name, (lo, hi) in bounds.items():
            if lo <= x < hi:
                out[name].append(text)
                break
    return {k: " ".join(v) for k, v in out.items()}


def anchored_bounds(
    rows: list[Row], bounds: dict[str, tuple[float, float]], anchor: str, expected_x: float,
) -> dict[str, tuple[float, float]]:
    """Shift column bounds so they line up with where the header word `anchor` actually is.

    Counties re-export the same spreadsheet with different tools from month to month, which
    moves every column sideways by a few points. Bounds are written against a reference file
    in which `anchor` starts at `expected_x`.
    """
    xs = [x for row in rows for x, t in row if t == anchor]
    if not xs:
        raise ValueError(f"Header word {anchor!r} not found; the list layout may have changed")
    dx = xs[0] - expected_x
    return {k: (lo + dx, hi + dx) for k, (lo, hi) in bounds.items()}


_VS_RE = re.compile(r"\bvs\.?\s|\bv\.\s", re.I)
# A bare "V" only counts as "versus" right after the government party, so a middle initial
# ("JOHN V SMITH") is left alone.
_GOV_V_RE = re.compile(r"\b(county|city|state|district|isd|of)\s+v\s", re.I)
_ETAL_RE = re.compile(r",?\s*\bet\.?\s*al\.?\b.*$|\s+etal\b.*$", re.I)


def owner_from_style(style: str) -> str:
    """'DALLAS COUNTY ET AL VS JOHN DOE ETAL' -> 'JOHN DOE' (the defendant in a tax suit)."""
    style = re.sub(r"\s+", " ", style)
    parts = _VS_RE.split(style, maxsplit=1)
    if len(parts) == 1:
        parts = _GOV_V_RE.split(style, maxsplit=1)
        parts = [parts[0], parts[-1]] if len(parts) > 1 else parts
    defendant = parts[1] if len(parts) == 2 else parts[0]
    return _ETAL_RE.sub("", defendant).strip(" ,.")
