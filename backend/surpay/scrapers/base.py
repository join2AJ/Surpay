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
