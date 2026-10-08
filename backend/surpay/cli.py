"""Command line: python -m surpay.cli <command>

  init-db                       create tables
  sources                       list available scrapers
  scrape [NAME ...] [--all] [--if-stale HOURS]
                                run scrapers (schedule daily); --if-stale skips sources
                                that succeeded within HOURS
  import-file PATH ...          load a CSV/XLSX list (see scrapers/file_import.py)
  stats                         summary of what's in the database
  sync-counties                 load data/county_sources.csv into the database
  check-sources                 fetch every county list URL and report which ones changed
  counties                      summary of the county registry
  seed-demo [--remove]          add (or remove) fictional "Demo County" records
"""

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from . import counties
from .db import SessionLocal, init_db
from .ingest import run_source, upsert
from .models import ScrapeRun, SurplusRecord
from .scrapers import SOURCES, RecordIn
from .scrapers.file_import import records_from_file


def _dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _recently_ok(session, source: str, hours: float) -> bool:
    last = session.scalar(
        select(ScrapeRun.finished_at).where(ScrapeRun.source == source, ScrapeRun.ok.is_(True))
        .order_by(ScrapeRun.id.desc()).limit(1)
    )
    if last is None:
        return False
    if last.tzinfo is None:  # SQLite drops the timezone
        last = last.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last < timedelta(hours=hours)


def _demo_records() -> list[RecordIn]:
    """Fictional people and places in 'Demo County' so they can't be mistaken for real records."""
    rows = [
        ("D-1001", "Jordan Testwell", "412 Maple Ridge Rd, Springfield, OH 45501", 2_845_000, date(2024, 6, 17)),
        ("D-1002", "TESTWELL, JORDAN A", "88 Harbor View Dr, Springfield, OH 45502", 612_550, date(2023, 11, 6)),
        ("D-1003", "Casey Placeholder", "19 Elm St, Springfield, OH 45503", 1_210_000, date(2024, 2, 12)),
        ("D-1004", "Morgan & Riley Example", "7 Birch Ct, Springfield, OH 45504", 4_390_075, date(2024, 9, 9)),
        ("D-1005", "Avery Sampleton", "230 Lake Shore Blvd, Springfield, OH 45505", 98_013, date(2025, 1, 21)),
    ]
    return [
        RecordIn(source_key=key, state="OH", county="Demo", sale_type="tax_sale", reference=f"Case {key}",
                 owner_name=name, owner_address=addr, amount_cents=cents, sale_date=sold,
                 source_url="", raw={"demo": True})
        for key, name, addr, cents, sold in rows
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="surpay")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    sub.add_parser("sources")
    s = sub.add_parser("scrape")
    s.add_argument("names", nargs="*")
    s.add_argument("--all", action="store_true")
    s.add_argument("--if-stale", type=float, metavar="HOURS")
    f = sub.add_parser("import-file")
    f.add_argument("path", type=Path)
    f.add_argument("--state", required=True)
    f.add_argument("--county", required=True)
    f.add_argument("--sale-type", choices=["tax_sale", "mortgage_foreclosure"], required=True)
    f.add_argument("--name", required=True, help="column holding the owner name")
    f.add_argument("--amount", required=True, help="column holding the surplus amount")
    f.add_argument("--reference", required=True, help="column holding case or parcel number")
    f.add_argument("--address", help="column holding the owner address")
    f.add_argument("--sale-date", help="column holding the sale date")
    f.add_argument("--source-url", default="")
    f.add_argument("--partial", action="store_true",
                   help="file is not the county's complete list; don't delist missing records")
    sub.add_parser("stats")
    sub.add_parser("sync-counties")
    sub.add_parser("check-sources")
    sub.add_parser("counties")
    d = sub.add_parser("seed-demo")
    d.add_argument("--remove", action="store_true")
    args = p.parse_args(argv)

    init_db()
    with SessionLocal() as session:
        if args.cmd == "init-db":
            print("Database ready.")
        elif args.cmd == "sources":
            for name, cls in SOURCES.items():
                print(f"{name:20} {cls.description}")
        elif args.cmd == "scrape":
            names = list(SOURCES) if args.all else args.names
            if not names:
                p.error("give source names or --all")
            failed = False
            for name in names:
                if name not in SOURCES:
                    p.error(f"unknown source {name!r}; see `sources`")
                if args.if_stale is not None and _recently_ok(session, name, args.if_stale):
                    print(f"{name}: skipped, scraped within {args.if_stale:g}h")
                    continue
                run = run_source(session, name)
                if run.ok:
                    print(f"{name}: +{run.added} new, {run.updated} updated, {run.delisted} delisted")
                else:
                    failed = True
                    print(f"{name}: FAILED {run.error}", file=sys.stderr)
            return 1 if failed else 0
        elif args.cmd == "import-file":
            records = records_from_file(
                args.path, state=args.state, county=args.county, sale_type=args.sale_type,
                name_col=args.name, amount_col=args.amount, reference_col=args.reference,
                address_col=args.address, sale_date_col=args.sale_date, source_url=args.source_url,
            )
            source = f"file:{args.state.lower()}_{args.county.lower().replace(' ', '_')}"
            run = upsert(session, source, records, full_snapshot=not args.partial)
            print(f"{source}: read {len(records)} rows; +{run.added} new, {run.updated} updated, "
                  f"{run.delisted} delisted")
        elif args.cmd == "sync-counties":
            added, updated = counties.sync_from_csv(session)
            print(f"county registry: +{added} new, {updated} updated")
        elif args.cmd == "check-sources":
            changed = counties.check_sources(session)
            for c in changed:
                print(f"CHANGED  {c.county}, {c.state}: {c.list_url}")
            print(f"{len(changed)} county lists changed since the last check")
        elif args.cmd == "counties":
            s = counties.summary(session)
            print(f"{s['total']} counties in registry")
            for status, n in s["by_status"].most_common():
                print(f"  {status:16} {n}")
            print("researched by difficulty:", dict(s["by_difficulty"]))
            print("states researched:", ", ".join(s["states_researched"]))
        elif args.cmd == "seed-demo":
            run = upsert(session, "demo", [] if args.remove else _demo_records(), full_snapshot=True)
            print(f"demo: +{run.added} new, {run.updated} updated, {run.delisted} removed")
        elif args.cmd == "stats":
            rows = session.execute(
                select(SurplusRecord.state, SurplusRecord.county, func.count(), func.sum(SurplusRecord.amount_cents))
                .where(SurplusRecord.status == "listed")
                .group_by(SurplusRecord.state, SurplusRecord.county)
            ).all()
            for state, county, n, total in rows:
                print(f"{county} County, {state}: {n} records, {_dollars(total)}")
            last = session.scalars(select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(5)).all()
            for r in last:
                print(f"  run {r.source} {r.started_at:%Y-%m-%d %H:%M} ok={r.ok} {r.error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
