"""Rebuild data/county_sources.csv: every US county, with our research merged in.

    python scripts/build_county_registry.py

Downloads the Census Bureau's county list (50 states + DC, 3,143 counties and equivalents)
and overlays data/county_research.csv. Edit the research file, not the output.
"""

import csv
import io
import sys
import urllib.request
from pathlib import Path

CENSUS_URL = "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"
TERRITORIES = {"PR", "VI", "GU", "AS", "MP", "UM"}
DATA = Path(__file__).resolve().parent.parent / "data"
FIELDS = ["fips", "state", "county", "status", "difficulty", "publisher", "format", "list_url",
          "update_frequency", "scraper", "notes", "last_verified"]
SUFFIXES = (" County", " Parish", " Borough", " Census Area", " Municipality", " City and Borough",
            " city", " Planning Region")


def short_name(name: str) -> str:
    for s in SUFFIXES:
        if name.endswith(s):
            return name[: -len(s)]
    return name


def main() -> int:
    raw = urllib.request.urlopen(CENSUS_URL, timeout=60).read().decode("latin-1")
    census = [r for r in csv.DictReader(io.StringIO(raw), delimiter="|") if r["STATE"] not in TERRITORIES]

    with (DATA / "county_research.csv").open(newline="") as f:
        research = list(csv.DictReader(f))

    rows, index = [], {}
    for c in census:
        row = {k: "" for k in FIELDS}
        row.update(fips=c["STATEFP"] + c["COUNTYFP"], state=c["STATE"], county=c["COUNTYNAME"],
                   status="unresearched", difficulty="unknown")
        rows.append(row)
        # "Baltimore County" and "Baltimore city" both exist; the County form wins the short key.
        key = (c["STATE"], short_name(c["COUNTYNAME"]).lower())
        if key not in index or c["COUNTYNAME"].endswith(" County"):
            index[key] = row

    missing = []
    for r in research:
        row = index.get((r["state"], r["county"].lower()))
        if row is None:
            missing.append(f"{r['county']}, {r['state']}")
            continue
        row.update({k: v for k, v in r.items() if k not in ("state", "county")})

    with (DATA / "county_sources.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} counties written; {len(research) - len(missing)} with research")
    if missing:
        print("Not matched to a Census county:", ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
