from datetime import date

from surpay.ingest import upsert
from tests.conftest import verify_identity
from surpay.scrapers.base import RecordIn


def seed(session):
    upsert(session, "adams_oh", [
        RecordIn(source_key="1", state="OH", county="Adams", sale_type="tax_sale",
                 reference="Parcel 029-00-00-049.000", owner_name="Robert Sample",
                 owner_address="6063 State Route 73, Peebles, OH 45660", amount_cents=1973260,
                 sale_date=date(2024, 7, 1), source_url="https://example/list.docx"),
        RecordIn(source_key="2", state="OH", county="Adams", sale_type="tax_sale",
                 reference="Parcel 1", owner_name="Someone Else", owner_address="", amount_cents=500,
                 sale_date=None, source_url=""),
    ], full_snapshot=True)


def signup(client, email="rob@example.com", name="Robert Sample", verified=True):
    r = client.post("/auth/signup", json={"email": email, "password": "correct horse", "full_name": name})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    if verified:
        verify_identity(client, h, name)
    return h


def test_full_flow(client, session):
    seed(session)
    assert client.get("/coverage").json() == {"records": 2, "total_amount_cents": 1973760,
                                              "counties": ["Adams County, OH"], "demo_login": False}
    h = signup(client)

    m = client.get("/me/matches", headers=h).json()
    assert len(m["matches"]) == 1
    first = m["matches"][0]
    assert first["confidence"] == "likely"
    assert first["amount_cents"] == 1973260
    assert first["fee_pct"] == 15.0
    assert first["estimated_net_cents"] == 1973260 - round(1973260 * 0.15)
    assert m["records_searched"] == 2

    r = client.put("/me", headers=h, json={
        "full_name": "Robert Sample", "other_names": [], "phone": "",
        "addresses": [{"street": "6063 St Rte 73", "city": "Peebles", "state": "oh", "zip": "45660",
                       "county": "Adams County"}],
    })
    assert r.status_code == 200 and r.json()["addresses"][0]["state"] == "OH"
    m = client.get("/me/matches", headers=h).json()
    assert m["matches"][0]["confidence"] == "strong"

    rid = m["matches"][0]["record_id"]
    c = client.post("/me/claims", headers=h, json={"record_id": rid})
    # ID was verified at sign-up, so the only thing left is signing the agreement
    assert c.status_code == 201 and c.json()["status"] == "identity_submitted"
    assert c.json()["next_action"] == "sign_agreement"
    # idempotent
    assert client.post("/me/claims", headers=h, json={"record_id": rid}).json()["id"] == c.json()["id"]
    assert client.get("/me/matches", headers=h).json()["matches"][0]["claim_status"] == "identity_submitted"
    assert len(client.get("/me/claims", headers=h).json()) == 1


def test_cannot_claim_someone_elses_record(client, session):
    seed(session)
    h = signup(client)
    other_id = 2
    assert client.post("/me/claims", headers=h, json={"record_id": other_id}).status_code == 404


def test_auth_errors(client):
    signup(client)
    assert client.post("/auth/signup", json={"email": "rob@example.com", "password": "correct horse",
                                             "full_name": "Rob Two"}).status_code == 409
    assert client.post("/auth/login", json={"email": "rob@example.com", "password": "nope"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ROB@example.com",
                                            "password": "correct horse"}).status_code == 200
    assert client.get("/me/matches").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_demo_login_off_by_default(client):
    assert client.get("/coverage").json()["demo_login"] is False
    assert client.post("/auth/demo").status_code == 404


def test_demo_login_one_tap(client, monkeypatch):
    from surpay import config

    monkeypatch.setattr(config, "DEMO_ENABLED", True)
    assert client.get("/coverage").json()["demo_login"] is True

    r = client.post("/auth/demo")
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert r.json()["user"]["full_name"] == "Jordan Testwell"

    m = client.get("/me/matches", headers=h).json()
    assert [x["confidence"] for x in m["matches"]] == ["strong", "likely"]
    assert m["total_amount_cents"] == 2_845_000 + 612_550

    assert r.json()["user"]["identity_status"] == "approved"  # demo is pre-verified

    # A tester starts a claim and edits the profile; the next demo sign-in starts fresh.
    client.post("/me/claims", headers=h, json={"record_id": m["matches"][0]["record_id"]})
    client.put("/me", headers=h, json={"full_name": "Jordan Testwell", "other_names": [], "phone": "", "addresses": []})
    r2 = client.post("/auth/demo").json()
    h2 = {"Authorization": f"Bearer {r2['token']}"}
    assert r2["user"]["full_name"] == "Jordan Testwell" and len(r2["user"]["addresses"]) == 1
    assert client.get("/me/claims", headers=h2).json() == []


def test_results_locked_until_identity_approved(client, session):
    """A broker can't sign up and look up someone else: nothing shows until their own ID is approved,
    and the search only ever uses the name on that ID."""
    seed(session)
    h = signup(client, email="broker@example.com", name="Robert Sample", verified=False)
    assert client.get("/me/matches", headers=h).status_code == 403
    assert client.get("/me/matches/preview", headers=h).json() == {"identity_status": None, "possible_matches": 0}

    # They submit their own ID; it's pending review: a count only, no amounts or details
    verify_identity(client, h, "Bobby Broker", approve=False)
    assert client.get("/me/matches", headers=h).status_code == 403
    assert client.get("/me/matches/preview", headers=h).json() == {"identity_status": "pending", "possible_matches": 0}
    assert client.post("/me/claims", headers=h, json={"record_id": 1}).status_code == 403

    # And they can't swap in someone else's name now
    r = client.put("/me", headers=h, json={"full_name": "Robert Sample", "other_names": ["Robert Sample"],
                                           "phone": "", "addresses": []})
    assert r.status_code == 409
    me = client.get("/me", headers=h).json()
    assert me["name_locked"] is True and me["identity_status"] == "pending"


def test_legal_basis_on_matches(client, session):
    seed(session)
    h = signup(client)
    m = client.get("/me/matches", headers=h).json()["matches"][0]
    assert m["legal"]["law"] == "Ohio Revised Code § 5721.20"
    assert any("W-9" in p for p in m["legal"]["proof"])
    assert "3 years" in m["legal"]["deadline"]
