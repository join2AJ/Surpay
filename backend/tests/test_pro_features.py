"""Staff overview, records browser, exports, suspension, notes; attorney profile and document requests."""

from tests.conftest import TEST_JPEG
from tests.test_attorneys import admin, attorney, claimant_with_claim, signup  # noqa: F401  (fixture)

ACCEPT = {"conflict_checked": True}


def accepted(client, session, admin):  # noqa: F811
    ah, auid = attorney(client, admin, "alex@law.com", "Alex Counsel", ["Dallas County"])
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"})
    ch, claim = claimant_with_claim(client, session)
    client.post(f"/attorney/cases/{claim['id']}/accept", headers=ah, json=ACCEPT)
    return ah, auid, ch, claim


def test_overview_counts_records_and_flags_work(client, session, admin):  # noqa: F811
    ah, auid, ch, claim = accepted(client, session, admin)
    o = client.get("/admin/overview", headers=admin).json()
    assert o["records"]["listed"] == 1 and o["records"]["total_cents"] == 2_000_000
    assert o["records"]["by_county"][0] == {"state": "TX", "county": "Dallas", "records": 1,
                                            "total_cents": 2_000_000, "largest_cents": 2_000_000}
    assert o["claims"]["by_status"] == {"attorney_assigned": 1} and o["claims"]["pipeline_fee_cents"] > 0
    assert o["people"]["attorneys_approved"] == 1 and o["people"]["ids_approved"] == 1
    assert {s["source"] for s in o["sources"]} >= {"dallas_tx"}
    assert any("isn't healthy" in a or "Scraper needs attention" in a for a in o["alerts"])
    assert o["registry"]["total"] >= 0


def test_records_browser_and_exports(client, session, admin):  # noqa: F811
    accepted(client, session, admin)
    r = client.get("/admin/records?q=jane sample", headers=admin).json()
    assert r["total"] == 1 and r["records"][0]["claims"] == 1 and r["records"][0]["deadline"] == "2027-01-07"
    assert client.get("/admin/records?state=OH", headers=admin).json()["total"] == 0
    csv_ = client.get("/admin/records.csv", headers=admin)
    assert csv_.status_code == 200 and "Jane Sample" in csv_.text and csv_.headers["content-type"].startswith("text/csv")
    claims_csv = client.get("/admin/claims.csv", headers=admin).text
    assert "SP-000001" in claims_csv and "Alex Counsel" in claims_csv


def test_suspending_an_account(client, session, admin):  # noqa: F811
    ah, auid, ch, claim = accepted(client, session, admin)
    [u] = client.get("/admin/users?q=jane", headers=admin).json()
    assert u["identity"] == "approved" and u["claims"] == 1
    assert client.post(f"/admin/users/{u['id']}/suspend", headers=admin, json={"decision": "rejected"}).status_code == 422
    client.post(f"/admin/users/{u['id']}/suspend", headers=admin, json={"decision": "rejected", "note": "broker"})
    assert client.get("/me", headers=ch).status_code == 401  # signed out
    r = client.post("/auth/login", json={"email": "jane@example.com", "password": "correct horse"})
    assert r.status_code == 403 and "suspended" in r.text
    client.post(f"/admin/users/{u['id']}/suspend", headers=admin, json={"decision": "approved"})
    assert client.post("/auth/login", json={"email": "jane@example.com", "password": "correct horse"}).status_code == 200

    # A suspended attorney's cases go back to the queue
    client.post(f"/admin/users/{auid}/suspend", headers=admin, json={"decision": "rejected", "note": "license lapsed"})
    assert client.get(f"/admin/claims", headers=admin).json()[0]["attorney"] is None


def test_staff_notes_are_private(client, session, admin):  # noqa: F811
    ah, auid, ch, claim = accepted(client, session, admin)
    notes = client.post(f"/admin/claims/{claim['id']}/notes", headers=admin, json={"status": "", "note": "Called county"}).json()
    assert notes[0]["body"] == "Called county"
    assert "Called county" not in client.get(f"/me/claims/{claim['id']}", headers=ch).text
    assert "Called county" not in client.get(f"/attorney/cases/{claim['id']}", headers=ah).text


def test_attorney_profile_and_pause(client, session, admin):  # noqa: F811
    ah, auid = attorney(client, admin, "alex@law.com", "Alex Counsel", ["Dallas County"])
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"})
    assert client.put("/attorney/me", headers=ah, json={"counties": ["Atlantis County"]}).status_code == 422
    me = client.put("/attorney/me", headers=ah, json={"available": False, "firm": "New Firm LLP"}).json()
    assert me["available"] is False and me["firm"] == "New Firm LLP"
    ch, claim = claimant_with_claim(client, session)
    assert client.get("/attorney/cases", headers=ah).json() == []  # paused: no offers
    client.put("/attorney/me", headers=ah, json={"available": True})
    assert len(client.get("/attorney/cases", headers=ah).json()) == 1  # waiting case offered on return


def test_document_requests_round_trip(client, session, admin):  # noqa: F811
    ah, auid, ch, claim = accepted(client, session, admin)
    case = client.post(f"/attorney/cases/{claim['id']}/document-requests", headers=ah,
                       json={"kind": "w9", "note": "Sign page 1"}).json()
    [req] = case["document_requests"]
    assert req["label"] == "IRS Form W-9" and req["status"] == "requested" and case["reference_code"] == "SP-000001"
    mine = client.get(f"/me/claims/{claim['id']}", headers=ch).json()
    assert mine["document_requests"][0]["note"] == "Sign page 1"
    titles = [n["title"] for n in client.get("/me/notifications", headers=ch).json()["items"]]
    assert "Your attorney needs: IRS Form W-9" in titles

    mine = client.post(f"/me/claims/{claim['id']}/documents/{req['id']}", headers=ch, json={"image_b64": TEST_JPEG}).json()
    assert mine["document_requests"][0]["status"] == "uploaded"
    f = client.get(f"/attorney/cases/{claim['id']}/document-requests/{req['id']}/file", headers=ah)
    assert f.status_code == 200 and f.content.startswith(b"\xff\xd8")
    case = client.post(f"/attorney/cases/{claim['id']}/document-requests/{req['id']}/review", headers=ah,
                       json={"decision": "rejected", "note": "Unsigned"}).json()
    assert case["document_requests"][0]["status"] == "rejected"
    client.post(f"/me/claims/{claim['id']}/documents/{req['id']}", headers=ch, json={"image_b64": TEST_JPEG})
    case = client.post(f"/attorney/cases/{claim['id']}/document-requests/{req['id']}/review", headers=ah,
                       json={"decision": "accepted"}).json()
    assert case["document_requests"][0]["status"] == "accepted"
    assert client.post(f"/me/claims/{claim['id']}/documents/{req['id']}", headers=ch,
                       json={"image_b64": TEST_JPEG}).status_code == 409
    assert client.get(f"/attorney/cases/{claim['id']}/packet", headers=ah).content.startswith(b"%PDF")
