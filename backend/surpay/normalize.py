"""Name and address normalization so county spellings line up with what users type."""

import re

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "md", "esq"}
_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr"}
# Words that appear in owner fields but are not part of a person's name.
_NOISE = {"et", "al", "etal", "ux", "vir", "aka", "nka", "fka", "estate", "of", "the", "heirs", "unknown", "deceased", "and"}

_STREET_ABBR = {
    "street": "st", "avenue": "ave", "av": "ave", "road": "rd", "lane": "ln", "drive": "dr",
    "court": "ct", "circle": "cir", "boulevard": "blvd", "place": "pl", "terrace": "ter",
    "highway": "hwy", "parkway": "pkwy", "route": "rte", "rote": "rte", "rt": "rte",
    "north": "n", "south": "s", "east": "e", "west": "w", "trail": "trl", "way": "wy",
    "state": "st", "county": "co", "township": "twp",
}
_UNIT_RE = re.compile(r"\b(apt|unit|suite|ste|lot|#)\s*\w+\b")


def name_tokens(name: str) -> list[str]:
    """'SMITH, JOHN A. JR' -> ['john', 'a', 'smith']; drops suffixes, honorifics and filler."""
    name = name.lower().replace("&", " and ")
    if name.count(",") == 1:
        last, first = name.split(",")
        # Only treat as 'Last, First' when the part before the comma looks like a surname.
        if len(last.split()) <= 2 and first.strip():
            name = f"{first} {last}"
    tokens = re.findall(r"[a-z]+(?:'[a-z]+)?", name)
    return [t.replace("'", "") for t in tokens if t not in _SUFFIXES | _HONORIFICS | _NOISE]


def normalize_name(name: str) -> str:
    return " ".join(name_tokens(name))


def normalize_street(street: str) -> str:
    """'6063 State Route 73' and '6063 St Rte 73' both -> '6063 st rte 73'."""
    s = _UNIT_RE.sub(" ", street.lower())
    words = re.findall(r"[a-z0-9]+", s)
    return " ".join(_STREET_ABBR.get(w, w) for w in words)


def split_street_number(street: str) -> tuple[str, str]:
    norm = normalize_street(street)
    m = re.match(r"(\d+[a-z]?)\s+(.*)", norm)
    return (m.group(1), m.group(2)) if m else ("", norm)
