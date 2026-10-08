"""Start a claim -> submit ID -> sign agreement -> staff review -> filed -> paid."""

import base64
from datetime import date, datetime, timedelta, timezone

import pytest

from surpay import claims, config, crypto
from surpay.ingest import upsert
from surpay.models import IdentityVerification
from surpay.scrapers.base import RecordIn

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 400).decode()
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 400).decode()
ADDRESS = {"street": "412 Maple Ridge Rd", "city": "Springfield", "state": "OH", "zip": "45501",
           "county": "Demo County"}
IDENTITY = {
    "legal_name": "Jordan Testwell", "date_of_birth": "1980-04-02", "ssn_last4": "1234",
    "phone": "555-010-0000", "street": "9 New Home Ln", "city": "Columbus", "state": "oh", "zip": "43004",
    "id_type": "drivers_license", "id_front_b64": JPEG, "selfie_b64": PNG, "consent": True,
}


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "staff-secret")
    return {"X-Admin-Token": "staff-secret"}


@pytest.fixture
def user(client, session):
    upsert(session, "demo", [
        RecordIn(source_key="D1", state="OH", county="Demo", sale_type="tax_sale", reference="Case D1",
                 owner_name="Jordan Testwell", owner_address="412 Maple Ridge Rd, Springfield, OH",
                 amount_cents=2_845_000, sale_date=date(2024, 6, 17), source_url=""),
        RecordIn(source_key="D2", state="OH", county="Demo", sale_type="tax_sale", reference="Case D2",
                 owner_name="TESTWELL, JORDAN A", owner_address="", amount_cents=612_550,
                 sale_date=None, source_url=""),
    ], full_snapshot=True)
    r = client.post("/auth/signup", json={"email": "j@example.com", "password": "correct horse",
                                          "full_name": "Jordan Testwell"})
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.put("/me", headers=h, json={"full_name": "Jordan Testwell", "other_names": [], "phone": "",
                                              "addresses": [ADDRESS]}).status_code == 200
    ids = [m["record_id"] for m in client.get("/me/matches", headers=h).json()["matches"]]
    return h, ids


def steps(claim):
    return {s["status"]: s["state"] for s in claim["timeline"]}


def test_full_claim_flow(client, session, user, admin):
    h, (rid, rid2) = user
    c = client.post("/me/claims", headers=h, json={"record_id": rid}).json()
    assert c["next_action"] == "verify_identity"
    assert steps(c)["requested"] == "done" and steps(c)["identity_submitted"] == "current"
    assert c["estimated_completion_end"] is not None
    assert "approximate estimates" in c["disclaimer"]

    # Can't sign before the ID is in
    assert client.post(f"/me/claims/{c['id']}/agreement", headers=h,
                       json={"signature_name": "Jordan Testwell", "agreed": True}).status_code == 409

    # ID upload: stored encrypted, claim moves on
    [c] = client.post("/me/identity", headers=h, json=IDENTITY).json()
    assert c["status"] == "identity_submitted" and c["next_action"] == "sign_agreement"
    assert c["identity_status"] == "pending"
    stored = session.query(IdentityVerification).one()
    assert stored.state == "OH" and stored.id_front != base64.b64decode(JPEG)  # encrypted at rest
    assert crypto.decrypt(stored.id_front) == base64.b64decode(JPEG)

    agreement = client.get(f"/me/claims/{c['id']}/agreement", headers=h).json()
    assert not agreement["signed"] and "15%" in agreement["text"] and "Demo County" in agreement["text"]
    c = client.post(f"/me/claims/{c['id']}/agreement", headers=h,
                    json={"signature_name": "Jordan Testwell", "agreed": True}).json()
    assert c["status"] == "agreement_signed" and c["next_action"] is None
    assert client.get(f"/me/claims/{c['id']}/agreement", headers=h).json()["signed"] is True

    # A second claim reuses the identity already on file
    c2 = client.post("/me/claims", headers=h, json={"record_id": rid2}).json()
    assert c2["status"] == "identity_submitted" and c2["next_action"] == "sign_agreement"

    # Staff: review page and documents need the token
    assert client.get("/admin/claims").status_code == 401
    listing = client.get("/admin/claims", headers=admin).json()
    assert {x["id"] for x in listing} == {c["id"], c2["id"]}
    uid = listing[0]["user"]["id"]
    doc = client.get(f"/admin/users/{uid}/documents/selfie", headers=admin)
    assert doc.status_code == 200 and doc.headers["content-type"] == "image/png"

    # Approving the ID moves signed claims forward
    client.post(f"/admin/users/{uid}/identity", headers=admin, json={"decision": "approved"})
    c = client.get(f"/me/claims/{c['id']}", headers=h).json()
    assert c["status"] == "identity_verified" and c["identity_status"] == "approved"
    assert steps(c)["filed"] == "current"

    # Second claim signs later and goes straight to verified
    c2 = client.post(f"/me/claims/{c2['id']}/agreement", headers=h,
                     json={"signature_name": "Jordan Testwell", "agreed": True}).json()
    assert c2["status"] == "identity_verified"

    for s in ("filed", "approved", "paid"):
        client.post(f"/admin/claims/{c['id']}/status", headers=admin, json={"status": s, "note": f"{s} note"})
    c = client.get(f"/me/claims/{c['id']}", headers=h).json()
    assert c["status"] == "paid" and set(steps(c).values()) == {"done"}
    assert c["estimated_completion_end"] is None


def test_rejected_id_can_be_resubmitted(client, user, admin):
    h, (rid, _) = user
    claim_id = client.post("/me/claims", headers=h, json={"record_id": rid}).json()["id"]
    client.post("/me/identity", headers=h, json=IDENTITY)
    assert client.post("/me/identity", headers=h, json=IDENTITY).status_code == 409  # already submitted
    uid = client.get("/admin/claims", headers=admin).json()[0]["user"]["id"]
    client.post(f"/admin/users/{uid}/identity", headers=admin, json={"decision": "rejected", "note": "Photo is blurry"})

    c = client.get(f"/me/claims/{claim_id}", headers=h).json()
    assert c["next_action"] == "verify_identity" and c["identity_status"] == "rejected"
    assert c["identity_note"] == "Photo is blurry"
    [c] = client.post("/me/identity", headers=h, json=IDENTITY).json()
    assert c["status"] == "identity_submitted" and c["identity_status"] == "pending"


def test_identity_validation(client, user):
    h, (rid, _) = user
    client.post("/me/claims", headers=h, json={"record_id": rid})
    bad = [
        {**IDENTITY, "consent": False},
        {**IDENTITY, "ssn_last4": "12a4"},
        {**IDENTITY, "id_front_b64": base64.b64encode(b"GIF89a" + b"0" * 200).decode()},
        {**IDENTITY, "id_type": "library_card"},
    ]
    for body in bad:
        assert client.post("/me/identity", headers=h, json=body).status_code == 422


def test_admin_off_without_token(client):
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/claims", headers={"X-Admin-Token": ""}).status_code == 404


def test_admin_page_served(client, admin):
    r = client.get("/admin")
    assert r.status_code == 200 and "Surpay claims review" in r.text


def test_address_needs_county_and_zip(client, user):
    h, _ = user
    for missing in ("county", "zip", "city"):
        addr = {k: v for k, v in ADDRESS.items() if k != missing}
        r = client.put("/me", headers=h, json={"full_name": "Jordan Testwell", "other_names": [], "phone": "",
                                               "addresses": [addr]})
        assert r.status_code == 422, missing


def test_counties_endpoint(client, session):
    from surpay import counties
    counties.sync_from_csv(session)
    oh = client.get("/counties", params={"state": "oh"}).json()
    assert len(oh) == 88 and "Adams County" in oh


def test_timeline_estimates_move_forward():
    """Each upcoming step's window starts no earlier than the previous one, and never in the past."""
    from surpay.models import Claim, ClaimEvent

    c = Claim(status="identity_verified")
    long_ago = datetime.now(timezone.utc) - timedelta(days=400)
    c.events = [ClaimEvent(status=s, created_at=long_ago) for s in claims.ORDER[:4]]
    t = claims.timeline(c)
    upcoming = [s for s in t if s["estimate_start"]]
    assert [s["status"] for s in upcoming] == ["filed", "approved", "paid"]
    today = datetime.now(timezone.utc).date()
    assert all(s["estimate_start"] >= today for s in upcoming)
    assert upcoming[0]["estimate_end"] <= upcoming[1]["estimate_end"] <= upcoming[2]["estimate_end"]


def test_existing_database_gets_new_columns(tmp_path):
    """A database created before the county column existed (like the live one) is upgraded in place."""
    from sqlalchemy import create_engine, inspect, text

    from surpay.db import init_db

    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE previous_addresses (id INTEGER PRIMARY KEY, user_id INTEGER, "
                          "street VARCHAR(255), city VARCHAR(128), state VARCHAR(2), zip VARCHAR(10))"))
        conn.execute(text("INSERT INTO previous_addresses VALUES (1, 1, '1 Old St', 'X', 'OH', '45501')"))
    init_db(engine)
    init_db(engine)  # running again is harmless
    assert "county" in {c["name"] for c in inspect(engine).get_columns("previous_addresses")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT street, county FROM previous_addresses")).one() == ("1 Old St", "")
