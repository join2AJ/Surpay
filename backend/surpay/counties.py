"""The county source registry: which counties publish surplus lists, and watching them change."""

import csv
import hashlib
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CountySource
from .scrapers.base import http_client

REGISTRY_CSV = Path(__file__).resolve().parent.parent / "data" / "county_sources.csv"
_RESEARCH_FIELDS = ("state", "county", "status", "difficulty", "publisher", "format", "list_url",
                    "update_frequency", "scraper", "notes", "last_verified")


def sync_from_csv(session: Session, path: Path = REGISTRY_CSV) -> tuple[int, int]:
    """Upsert research columns from the CSV. Check results already in the database are kept."""
    existing = {c.fips: c for c in session.scalars(select(CountySource))}
    added = updated = 0
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            c = existing.get(row["fips"])
            if c is None:
                c = CountySource(fips=row["fips"])
                session.add(c)
                added += 1
            elif any(getattr(c, k) != row[k] for k in _RESEARCH_FIELDS):
                updated += 1
            for k in _RESEARCH_FIELDS:
                setattr(c, k, row[k])
    session.commit()
    return added, updated


def check_sources(session: Session, delay_seconds: float = 1.0) -> list[CountySource]:
    """Fetch every published list URL and record whether its content changed.

    Returns the counties whose list changed since the last check — usually a new list was
    posted, so it's worth reviewing by hand or writing a scraper. Counties with a live scraper
    are skipped: their scrape runs already track them.
    """
    targets = session.scalars(
        select(CountySource)
        .where(CountySource.list_url.like("http%"), CountySource.status != "scraper_live")
        .order_by(CountySource.fips)
    ).all()
    changed = []
    with http_client() as client:
        for c in targets:
            now = datetime.now(timezone.utc)
            c.last_checked = now
            try:
                r = client.get(c.list_url)
                c.last_http_status = r.status_code
                c.check_error = "" if r.status_code < 400 else f"HTTP {r.status_code}"
                if r.status_code < 400:
                    digest = hashlib.sha256(r.content).hexdigest()
                    if c.content_hash and digest != c.content_hash:
                        c.last_changed = now
                        changed.append(c)
                    c.content_hash = digest
            except Exception as e:  # noqa: BLE001 — record any network failure on the row
                c.last_http_status = None
                c.check_error = f"{type(e).__name__}: {e}"[:500]
            session.commit()
            time.sleep(delay_seconds)
    return changed


def summary(session: Session) -> dict:
    rows = session.scalars(select(CountySource)).all()
    return {
        "total": len(rows),
        "by_status": Counter(r.status for r in rows),
        "by_difficulty": Counter(r.difficulty for r in rows if r.status != "unresearched"),
        "states_researched": sorted({r.state for r in rows if r.status != "unresearched"}),
    }
