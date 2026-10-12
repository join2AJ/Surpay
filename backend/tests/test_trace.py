"""Finding owners (at most four places per record, then move on) and inviting them to claim."""

import io
from datetime import date

from pypdf import PdfReader

from surpay import config, trace
from surpay.ingest import upsert
from surpay.scrapers.base import RecordIn
from tests.conftest import verify_identity
from tests.test_attorneys import admin, signup  # noqa: F401  (fixture)


def rec(key, owner, address="", cents=5_000_000):
    return RecordIn(source_key=key, state="TX", county="Dallas", sale_type="tax_sale", reference=f"Case {key}",
                    owner_name=owner, owner_address=address, amount_cents=cents, sale_date=date(2025, 6, 1),
                    source_url="https://example/list.pdf")


def test_names_from_county_lists():
    assert trace.person_name("TESTWELL, JORDAN A") == ("Jordan A Testwell", False)
    assert trace.person_name("ESTATE OF MARY PARENT") == ("Mary Parent", True)
    assert trace.person_name("JOHN DOE AND JANE DOE") == ("John Doe", False)
    assert trace.person_name("Morgan & Riley Example") == ("Morgan Example", False)
    assert trace.person_name("ACME HOLDINGS LLC")[0] is None


def test_classify_search_results():
    results = [
        {"title": "Jordan Testwell obituary - Dallas, TX", "url": "https://www.legacy.com/us/obituaries/x", "snippet": "Jordan Testwell of Dallas"},
        {"title": "Jordan Testwell - LinkedIn", "url": "https://www.linkedin.com/in/jt", "snippet": "Dallas, Texas"},
        {"title": "Jordan Testwell in Dallas TX", "url": "https://www.truepeoplesearch.com/find/x", "snippet": "Age 45"},
        {"title": "Contact Jordan Testwell", "url": "https://example.com", "snippet": "Email jordan.testwell@example.com TX"},
        {"title": "Somebody else", "url": "https://example.com/2", "snippet": "no match"},
    ]
    kinds = [x["kind"] for x in trace.classify(results, "Jordan Testwell", "Dallas", "TX")]
    assert kinds == ["obituary", "profile", "link", "email"]


def test_trace_stops_early_and_records_every_place(client, session, admin, monkeypatch):  # noqa: F811
    upsert(session, "dallas_tx", [rec("A", "SAMPLE, JANE", "12 Oak St, Dallas, TX 75201"), rec("B", "Pat Unknown", "", 4_000_000),
                                  rec("C", "ACME HOLDINGS LLC", "", 3_000_000)], full_snapshot=True)
    h = signup(client, "jane@example.com", "Jane Sample")
    verify_identity(client, h, "Jane Sample")
    monkeypatch.setattr(config, "BRAVE_API_KEY", "test")
    calls = []

    def fake_search(q):
        calls.append(q)
        if "obituary" in q:
            return [{"title": "Pat Unknown Obituary - Dallas", "url": "https://legacy.com/o/1", "snippet": "Pat Unknown of Dallas, TX"}]
        return [{"title": "Pat Unknown - LinkedIn", "url": "https://www.linkedin.com/in/pu", "snippet": "Dallas, TX"}]
    monkeypatch.setattr(trace, "web_search", fake_search)

    from surpay.models import SurplusRecord
    by_record = {session.get(SurplusRecord, run.record_id).owner_name: run for run in trace.trace_batch(session, limit=10)}
    jane = by_record["SAMPLE, JANE"]
    assert jane.status == "user_found" and len(jane.steps) == 1  # found on the first place: stop
    pat = by_record["Pat Unknown"]
    assert pat.status == "leads" and pat.deceased and [s["source"] for s in pat.steps] == [
        "Surpay users", "County list address", "Web search (brave)", "Obituary search (brave)"]  # four places, then stop
    assert by_record["ACME HOLDINGS LLC"].status == "business"
    assert len(calls) == 2  # only Pat was searched on the web
    assert trace.queue(session) == []  # all traced: the queue moves on
    titles = [n["title"] for n in client.get("/me/notifications", headers=h).json()["items"]]
    assert "We found money that may be yours" in titles


def test_staff_tools_letters_and_opt_out(client, session, admin):  # noqa: F811
    upsert(session, "dallas_tx", [rec("A", "Pat Unknown", "12 Oak St, Dallas, TX 75201")], full_snapshot=True)
    rid = client.get("/admin/records", headers=admin).json()["records"][0]["id"]
    t = client.post(f"/admin/records/{rid}/trace", headers=admin).json()
    assert t["runs"][0]["status"] == "leads" and t["search_provider"] is None
    assert any(s["name"] == "LinkedIn people search" for s in t["manual_sources"])
    address = [c for c in t["contacts"] if c["kind"] == "address"][0]
    t = client.post(f"/admin/records/{rid}/contacts", headers=admin,
                    json={"kind": "email", "value": "pat@example.com", "note": "From the obituary"}).json()
    assert any(c["kind"] == "email" and c["source"] == "manual" for c in t["contacts"])
    assert any(m["name"] == "National Public Data" and "site%3Anationalpublicdata.com" in m["url"] for m in t["manual_sources"])
    t = client.post(f"/admin/records/{rid}/contacts", headers=admin, json={
        "kind": "phone", "value": "555-010-1234", "note": "nationalpublicdata.com", "matches_property": True}).json()
    phone = [c for c in t["contacts"] if c["kind"] == "phone"][0]
    assert phone["confidence"] == "high" and "includes the sold property" in phone["note"]

    o = client.post(f"/admin/records/{rid}/outreach", headers=admin, json={"channel": "letter", "contact_id": address["id"]}).json()
    assert o["status"] == "ready" and len(o["code"]) == 8
    pdf = client.get("/admin/outreach/letters.pdf", headers=admin)
    text = PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert "Dear Pat Unknown" in text and o["code"] in text and "$" not in text.split("Kind regards")[0]
    assert client.post("/admin/outreach/mark-sent", headers=admin, json={"ids": [o["id"]]}).json()["marked"] == 1

    page = client.get(f"/i/{o['code']}")
    assert page.status_code == 200 and o["code"] in page.text
    h = client.post("/auth/signup", json={"email": "pat@example.com", "password": "correct horse battery",
                                          "full_name": "Pat Unknown", "accept_terms": True, "invite_code": o["code"].lower()})
    assert h.status_code == 201
    assert client.get("/admin/outreach", headers=admin).json()[0]["status"] == "signed_up"

    client.post(f"/optout/{o['code']}")
    r = client.post(f"/admin/records/{rid}/outreach", headers=admin, json={"channel": "letter", "contact_id": address["id"]})
    assert r.status_code == 409  # they asked not to be contacted


def test_admin_demo_can_find_owners_of_real_records(client, session, monkeypatch):
    from tests.test_demo_admin import demo_admin
    from surpay import trace_api
    monkeypatch.setattr(config, "DEMO_ENABLED", True)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "real-staff-token")
    staff = {"X-Admin-Token": "real-staff-token"}
    upsert(session, "dallas_tx", [rec("A", "Pat Unknown", "12 Oak St, Dallas, TX 75201")], full_snapshot=True)
    rid = client.get("/admin/records", headers=staff).json()["records"][0]["id"]
    client.post(f"/admin/records/{rid}/contacts", headers=staff, json={"kind": "email", "value": "pat@example.com"})
    d = demo_admin(client)

    t = client.post(f"/admin/records/{rid}/trace", headers=d)
    assert t.status_code == 200 and t.json()["read_only"] is True
    emails = [c["value"] for c in t.json()["contacts"] if c["kind"] == "email"]
    assert emails == ["p•••@example.com"]  # partly hidden in the demo
    assert any(s["name"] == "LinkedIn people search" for s in t.json()["manual_sources"])
    assert client.post("/admin/trace/run", headers=d, json={"limit": 10}).status_code == 200
    # Acting on a real person stays with staff
    assert client.post(f"/admin/records/{rid}/contacts", headers=d, json={"kind": "email", "value": "x@y.com"}).status_code == 404
    assert client.post(f"/admin/records/{rid}/outreach", headers=d, json={"channel": "letter"}).status_code == 404
    # And the demo's searches are capped
    monkeypatch.setattr(trace_api, "DEMO_TRACES_PER_HOUR", 1)
    assert client.post(f"/admin/records/{rid}/trace", headers=d).status_code == 429
    assert client.post(f"/admin/records/{rid}/trace", headers=staff).status_code == 200


def test_paste_contacts(client, session, admin):  # noqa: F811
    upsert(session, "dallas_tx", [rec("A", "SAMIYA MUSTAFA", "3920 WESTBROOK RD, Gwinnett County, GA")], full_snapshot=True)
    rid = client.get("/admin/records", headers=admin).json()["records"][0]["id"]
    url = "https://nationalpublicdata.com/people/m/samiya-mustafa/tx/houston/abc/"
    text = (f"record_id,kind,value,source_url,note,matches_property\n"
            f'{rid},email,s.m@example.com,{url},"National Public Data, current email",yes\n'
            f'{rid},phone,(555) 010-0000,{url},"Landline, Georgia",yes\n'
            f'{rid},address,"Houston, TX 77263",{url},Current city,yes\n'
            f"{rid},email,s.m@example.com,{url},again,yes\n"
            f"999,email,x@y.com,,,\n"
            f"{rid},fax,123,,,\n")
    r = client.post("/admin/contacts-import", headers=admin, json={"text": text}).json()
    assert r["added"] == 3
    assert [x["error"] for x in r["results"] if not x["ok"]] == ["Already saved", "Record 999 not found",
                                                                  "Type must be one of address, email, link, obituary, phone, profile"]
    t = client.get(f"/admin/records/{rid}/trace", headers=admin).json()
    addr = [c for c in t["contacts"] if c["kind"] == "address" and c["source"] == "manual"][0]
    assert addr["value"] == "Houston, TX 77263" and addr["confidence"] == "high" and addr["source_url"] == url
    assert "National Public Data, current email" in [c for c in t["contacts"] if c["kind"] == "email"][0]["note"]
