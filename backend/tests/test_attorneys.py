"""Attorney enrollment, verification, case allotment by county, and per-case payout."""

import base64
from datetime import date

import pytest

from surpay import config
from surpay.ingest import upsert
from surpay.scrapers.base import RecordIn
from tests.conftest import SIGNATURE_PNG, verify_identity

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 300).decode()


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "staff")
    return {"X-Admin-Token": "staff"}


def signup(client, email, name, role="claimant"):
    r = client.post("/auth/signup", json={"email": email, "password": "correct horse", "accept_terms": True, "full_name": name, "role": role})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == role
    return {"Authorization": f"Bearer {r.json()['token']}"}


def apply(client, h, counties, state="TX", name="Alex Counsel"):
    return client.post("/attorney/apply", headers=h, json={
        "full_name": name, "bar_state": state, "bar_number": "24012345", "firm": "Counsel PLLC",
        "phone": "214-555-0100", "office_address": "1 Main St, Dallas, TX 75201", "counties": counties,
        "bar_card_b64": JPEG, "accept_terms": True,
    })


def attorney(client, admin, email, name, counties, state="TX"):
    h = signup(client, email, name, role="attorney")
    assert apply(client, h, counties, state, name).status_code == 200
    uid = client.get("/me", headers=h).json()["id"]
    return h, uid


def claimant_with_claim(client, session, email="jane@example.com"):
    """A verified claimant with a signed agreement on a Dallas, TX record."""
    upsert(session, "dallas_tx", [RecordIn(
        source_key="TX-1", state="TX", county="Dallas", sale_type="tax_sale", reference="Case TX-21-0001",
        owner_name="Jane Sample", owner_address="", amount_cents=2_000_000, sale_date=date(2025, 1, 7),
        source_url="https://example/list.pdf")], full_snapshot=True)
    h = signup(client, email, "Jane Sample")
    verify_identity(client, h, "Jane Sample")
    rid = client.get("/me/matches", headers=h).json()["matches"][0]["record_id"]
    claim = client.post("/me/claims", headers=h, json={"record_id": rid}).json()
    claim = client.post(f"/me/claims/{claim['id']}/agreement", headers=h,
                        json={"signature_name": "Jane Sample", "agreed": True, "signature_png_b64": SIGNATURE_PNG}).json()
    assert claim["status"] == "identity_verified"
    return h, claim


def test_attorney_enrollment_and_case_flow(client, session, admin):
    # Attorney applies; nothing is offered until staff verify the bar license
    ah, auid = attorney(client, admin, "alex@law.com", "Alex Counsel", ["Dallas County", "Collin County"])
    me = client.get("/attorney/me", headers=ah).json()
    assert me["status"] == "pending" and me["fee_per_case_cents"] == 50000 and "independent professional judgment" in me["terms"]
    assert client.get("/attorney/cases", headers=ah).status_code == 403
    pending = client.get("/admin/attorneys", headers=admin).json()
    assert [p["user_id"] for p in pending] == [auid]
    assert client.get(f"/admin/attorneys/{auid}/bar-card", headers=admin).status_code == 200

    # A claimant's verified claim waits unassigned...
    ch, claim = claimant_with_claim(client, session)
    assert claim["attorney"] is None

    # ...until the attorney is approved, then it's offered to them
    r = client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"}).json()
    assert r["cases_offered"] == 1
    [case] = client.get("/attorney/cases", headers=ah).json()
    assert case["assignment_status"] == "offered" and case["county"] == "Dallas" and case["fee_cents"] == 50000
    assert case["claimant"] is None  # no personal details before accepting
    assert client.get(f"/attorney/cases/{case['id']}/documents/selfie", headers=ah).status_code == 403

    # Accept: full details, documents, agreement
    case = client.post(f"/attorney/cases/{case['id']}/accept", headers=ah).json()
    assert case["claimant"]["name"] == "Jane Sample" and case["claimant"]["ssn_last4"] == "1234"
    assert case["agreement"]["signature_name"] == "Jane Sample"
    assert case["legal"]["law"] == "Texas Tax Code §§ 34.03 and 34.04"
    assert client.get(f"/attorney/cases/{case['id']}/documents/id_front", headers=ah).status_code == 200

    # The claimant sees who has their case
    mine = client.get(f"/me/claims/{claim['id']}", headers=ch).json()
    assert mine["attorney"]["name"] == "Alex Counsel" and mine["attorney"]["bar"] == "TX Bar #24012345"

    # Attorney reports progress; the claimant's timeline follows; fee falls due at the end
    for s in ("filed", "approved", "paid"):
        case = client.post(f"/attorney/cases/{case['id']}/status", headers=ah, json={"status": s, "note": f"{s}!"}).json()
    assert case["status"] == "paid" and case["payout_status"] == "due"
    assert client.get(f"/me/claims/{claim['id']}", headers=ch).json()["status"] == "paid"
    assert client.post(f"/attorney/cases/{case['id']}/status", headers=ah, json={"status": "filed"}).status_code == 409

    # Staff pay the attorney
    paid = client.post(f"/admin/claims/{claim['id']}/payout", headers=admin).json()
    assert paid["attorney"]["payout_status"] == "paid"


def test_cases_go_to_county_attorneys_least_busy_first_and_skip_decliners(client, session, admin):
    h1, a1 = attorney(client, admin, "a1@law.com", "Ann One", ["Dallas County"])
    h2, a2 = attorney(client, admin, "a2@law.com", "Bob Two", ["Dallas County"])
    h3, a3 = attorney(client, admin, "a3@law.com", "Cy Three", ["Harris County"])          # wrong county
    h4, a4 = attorney(client, admin, "a4@law.com", "Di Four", ["Dallas County"], state="GA")  # wrong state
    for uid in (a1, a2, a3, a4):
        client.post(f"/admin/attorneys/{uid}", headers=admin, json={"decision": "approved"})

    _, claim = claimant_with_claim(client, session)
    first = [uid for uid, h in ((a1, h1), (a2, h2)) if client.get("/attorney/cases", headers=h).json()]
    assert len(first) == 1
    assert client.get("/attorney/cases", headers=h3).json() == [] and client.get("/attorney/cases", headers=h4).json() == []

    # The one offered declines: it moves to the other Dallas attorney and never comes back
    decliner, other = (h1, h2) if first[0] == a1 else (h2, h1)
    cid = client.get("/attorney/cases", headers=decliner).json()[0]["id"]
    client.post(f"/attorney/cases/{cid}/decline", headers=decliner, json={"reason": "conflict"})
    assert client.get("/attorney/cases", headers=decliner).json() == []
    assert client.get("/attorney/cases", headers=other).json()[0]["id"] == cid

    # Other declines too: nobody left, waits for staff
    client.post(f"/attorney/cases/{cid}/decline", headers=other, json={})
    listing = {c["id"]: c for c in client.get("/admin/claims", headers=admin).json()}
    assert listing[cid]["attorney"] is None


def test_attorney_guards(client, admin):
    claimant = signup(client, "c@example.com", "Casey Claimant")
    assert apply(client, claimant, ["Dallas County"]).status_code == 403  # not an attorney account
    assert client.get("/attorney/cases", headers=claimant).status_code == 403

    ah = signup(client, "z@law.com", "Zed Lawyer", role="attorney")
    assert client.get("/attorney/me", headers=ah).status_code == 404  # not applied yet
    bad = apply(client, ah, [])  # must serve at least one county
    assert bad.status_code == 422
    assert apply(client, ah, ["Dallas County"]).status_code == 200
    assert apply(client, ah, ["Dallas County"]).status_code == 409  # already applied
    # Someone else's case id: not found
    assert client.get("/attorney/cases/999", headers=ah).status_code in (403, 404)
