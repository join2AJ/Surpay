import csv

import httpx

from surpay import counties
from surpay.models import CountySource

FIELDS = ["fips", "state", "county", "status", "difficulty", "publisher", "format", "list_url",
          "update_frequency", "scraper", "notes", "last_verified"]


def write_csv(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def test_real_registry_covers_every_county():
    with counties.REGISTRY_CSV.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3143
    assert len({r["fips"] for r in rows}) == 3143
    live = {r["scraper"] for r in rows if r["status"] == "scraper_live"}
    from surpay.scrapers import SOURCES
    assert live == set(SOURCES)  # every scraper is recorded, and every recorded one exists


def test_sync_keeps_check_results(session, tmp_path):
    p = tmp_path / "c.csv"
    write_csv(p, [{"fips": "39001", "state": "OH", "county": "Adams County", "status": "list_online",
                   "list_url": "https://example.gov/list"}])
    assert counties.sync_from_csv(session, p) == (1, 0)
    c = session.get(CountySource, "39001")
    c.content_hash = "abc"
    session.commit()
    write_csv(p, [{"fips": "39001", "state": "OH", "county": "Adams County", "status": "scraper_live",
                   "list_url": "https://example.gov/list"}])
    assert counties.sync_from_csv(session, p) == (0, 1)
    c = session.get(CountySource, "39001")
    assert (c.status, c.content_hash) == ("scraper_live", "abc")


def test_check_sources_detects_changes(session, tmp_path, monkeypatch):
    body = {"v": b"list v1"}

    def handler(request):
        if "broken" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, content=body["v"])

    monkeypatch.setattr(counties, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    p = tmp_path / "c.csv"
    write_csv(p, [
        {"fips": "00001", "state": "OH", "county": "A", "list_url": "https://example.gov/list"},
        {"fips": "00002", "state": "OH", "county": "B", "list_url": "https://example.gov/broken"},
        {"fips": "00003", "state": "OH", "county": "C", "list_url": "mailto:clerk@example.gov"},
    ])
    counties.sync_from_csv(session, p)

    assert counties.check_sources(session, delay_seconds=0) == []  # first sight is not a change
    assert counties.check_sources(session, delay_seconds=0) == []  # same content
    body["v"] = b"list v2"
    changed = counties.check_sources(session, delay_seconds=0)
    assert [c.fips for c in changed] == ["00001"]
    assert session.get(CountySource, "00002").check_error == "HTTP 404"
    assert session.get(CountySource, "00003").last_checked is None  # email-only, not fetched
