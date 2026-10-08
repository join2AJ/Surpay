"""Write scraped records into the database and track what dropped off the list."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ScrapeRun, SurplusRecord
from .normalize import normalize_name
from .scrapers import SOURCES, RecordIn

_FIELDS = ("state", "county", "sale_type", "reference", "owner_name", "owner_address",
           "amount_cents", "sale_date", "source_url", "raw")


def upsert(session: Session, source: str, records: list[RecordIn], *, full_snapshot: bool) -> ScrapeRun:
    """Insert new records and update changed ones.

    full_snapshot=True means `records` is the source's complete current list, so anything we
    hold for that source that is missing from it gets marked "delisted".
    """
    now = datetime.now(timezone.utc)
    run = ScrapeRun(source=source, started_at=now, added=0, updated=0, delisted=0)
    existing = {r.source_key: r for r in session.scalars(select(SurplusRecord).where(SurplusRecord.source == source))}
    seen = set()
    for rec in records:
        if rec.source_key in seen:
            continue
        seen.add(rec.source_key)
        row = existing.get(rec.source_key)
        if row is None:
            row = SurplusRecord(source=source, source_key=rec.source_key, first_seen=now)
            session.add(row)
            run.added += 1
        elif any(getattr(row, f) != getattr(rec, f) for f in _FIELDS if f != "raw") or row.status != "listed":
            run.updated += 1
        for f in _FIELDS:
            setattr(row, f, getattr(rec, f))
        row.owner_name_norm = normalize_name(rec.owner_name)
        row.status = "listed"
        row.last_seen = now

    if full_snapshot:
        for key, row in existing.items():
            if key not in seen and row.status == "listed":
                row.status = "delisted"
                run.delisted += 1

    run.ok = True
    run.finished_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    return run


def run_source(session: Session, name: str) -> ScrapeRun:
    source = SOURCES[name]()
    try:
        records = source.fetch()
        if not records:
            # An empty list almost always means the page layout changed, not that every
            # claim was paid. Don't delist everything on a parser failure.
            raise RuntimeError("Source returned no records; check the parser")
    except Exception as e:  # noqa: BLE001 — record any failure on the run
        run = ScrapeRun(source=name, ok=False, error=f"{type(e).__name__}: {e}",
                        finished_at=datetime.now(timezone.utc))
        session.add(run)
        session.commit()
        return run
    return upsert(session, name, records, full_snapshot=True)
