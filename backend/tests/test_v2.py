"""Audit trail, encryption at rest, signing evidence, chat, notifications, family claims, fees,
privacy rights and security controls."""

import base64
from datetime import date

from sqlalchemy import text

from surpay import audit
from surpay.db import engine, init_db
from surpay.ingest import upsert
from surpay.models import AuditLog, IdentityVerification
from surpay.scrapers.base import RecordIn
from tests.conftest import TEST_JPEG, verify_identity
from tests.test_attorneys import admin, attorney, claimant_with_claim, signup  # noqa: F401  (fixture)

ADDRESS = {"street": "77 Oak Ln", "city": "Dallas", "state": "TX", "zip": "75201", "county": "Dallas County"}


def offered_and_accepted(client, session, admin):  # noqa: F811
    ah, auid = attorney(client, admin, "alex@law.com", "Alex Counsel", ["Dallas County"])
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"})
    ch, claim = claimant_with_claim(client, session)
    [case] = client.get("/attorney/cases", headers=ah).json()
    return ah, ch, claim, case


def test_new_stages_chat_and_notifications(client, session, admin):  # noqa: F811
    ah, ch, claim, case = offered_and_accepted(client, session, admin)
    notes = client.get("/me/notifications", headers=ah).json()
    assert notes["items"][0]["kind"] == "case_offer" and notes["unread"] >= 1

    # Chat isn't open before the attorney accepts
    assert client.post(f"/me/claims/{claim['id']}/messages", headers=ch, json={"body": "hi"}).status_code == 409

    case = client.post(f"/attorney/cases/{case['id']}/accept", headers=ah, json={"conflict_checked": True}).json()
    assert case["status"] == "attorney_assigned" and case["chat_open"]
    assert "email" not in case["claimant"] and "phone" not in case["claimant"]
    assert case["filing_guide"]["online"].startswith("Online") and len(case["filing_guide"]["steps"]) >= 5
    mine = client.get(f"/me/claims/{claim['id']}", headers=ch).json()
    assert mine["status"] == "attorney_assigned" and mine["attorney"]["name"] == "Alex Counsel"
    assert mine["attorney"]["phone"] == ""  # contact goes through the app

    # Attorney writes first; the client can't start the conversation
    chat = client.get(f"/me/claims/{claim['id']}/messages", headers=ch).json()
    assert not chat["can_send"] and "first message" in chat["waiting_reason"] and chat["code_of_conduct"]
    assert client.post(f"/me/claims/{claim['id']}/messages", headers=ch, json={"body": "hi"}).status_code == 409
    r = client.post(f"/attorney/cases/{case['id']}/messages", headers=ah,
                    json={"body": "Hello Jane, I'm handling your claim. Call me at 214-555-0100"})
    assert r.status_code == 422 and "phone numbers" in r.text
    for leak in ("email me at jane@mail.com", "see www.example.com", "add me on WhatsApp", "jane at gmail dot com"):
        assert client.post(f"/attorney/cases/{case['id']}/messages", headers=ah, json={"body": leak}).status_code == 422
    r = client.post(f"/attorney/cases/{case['id']}/messages", headers=ah,
                    json={"body": "Hello Jane, I'm handling your claim for $20,000.00 from the 2025-01-07 sale."})
    assert r.status_code == 200, r.text
    chat = client.get(f"/me/claims/{claim['id']}/messages", headers=ch).json()
    assert chat["can_send"] and chat["messages"][0]["sender_role"] == "attorney"
    assert client.post(f"/me/claims/{claim['id']}/messages", headers=ch, json={"body": "Thank you!"}).status_code == 200
    raw = session.execute(text("SELECT body FROM messages")).scalars().all()
    assert all(b.startswith("gAAAAA") for b in raw)  # encrypted at rest

    # Each attorney update reaches the client; "paid" is a money-released notification
    for s in ("filed", "hearing_pending", "approved", "paid"):
        assert client.post(f"/attorney/cases/{case['id']}/status", headers=ah, json={"status": s}).status_code == 200
    kinds = [n["kind"] for n in client.get("/me/notifications", headers=ch).json()["items"]]
    assert kinds[0] == "money_released" and kinds.count("claim_update") >= 4
    titles = [n["title"] for n in client.get("/me/notifications", headers=ch).json()["items"]]
    assert "Waiting for the county or court" in titles and "An attorney has taken your case" in titles
    assert client.get("/me", headers=ch).json()["unread_notifications"] > 0
    client.post("/me/notifications/read", headers=ch)
    assert client.get("/me", headers=ch).json()["unread_notifications"] == 0

    # Printable packet
    pdf = client.get(f"/attorney/cases/{case['id']}/packet", headers=ah)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_attorney_can_hand_back_until_filed(client, session, admin):  # noqa: F811
    ah, ch, claim, case = offered_and_accepted(client, session, admin)
    client.post(f"/attorney/cases/{case['id']}/accept", headers=ah, json={"conflict_checked": True})
    assert client.post(f"/attorney/cases/{case['id']}/decline", headers=ah, json={}).status_code == 200
    assert client.get(f"/me/claims/{claim['id']}", headers=ch).json()["status"] == "identity_verified"


def test_audit_trail_records_and_detects_tampering(client, session, admin):  # noqa: F811
    headers = {"X-Device-Id": "a1b2c3", "X-Install-Id": "inst-9", "X-Device-Model": "Pixel 8",
               "X-OS-Version": "Android 15", "X-App-Version": "0.2.0"}
    r = client.post("/auth/signup", headers=headers, json={"email": "z@example.com", "password": "correct horse",
                                                            "full_name": "Zed Person", "accept_terms": True})
    assert r.status_code == 201
    entry = session.query(AuditLog).filter_by(action="account.created").one()
    assert entry.device_id == "a1b2c3/inst-9" and "Pixel 8" in entry.device_info and entry.ip_address
    assert client.get("/admin/audit/verify", headers=admin).json()["ok"] is True

    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_log SET ip_address = '6.6.6.6' WHERE action = 'account.created'"))
    session.expire_all()
    result = audit.verify(session)
    assert result["ok"] is False and result["broken_at"] == entry.id


def test_identity_details_encrypted_at_rest_and_legacy_rows_migrated(client, session):
    h = signup(client, "e@example.com", "Erin Example")
    verify_identity(client, h, "Erin Example")
    row = session.execute(text("SELECT date_of_birth, ssn_last4, phone, street FROM identity_verifications")).one()
    assert all(str(v).startswith("gAAAAA") for v in row)
    assert session.query(IdentityVerification).one().ssn_last4 == "1234"

    # A row saved before encryption existed is encrypted on the next start
    with engine.begin() as conn:
        conn.execute(text("UPDATE identity_verifications SET ssn_last4 = '9876', date_of_birth = '1970-01-02'"))
    init_db()
    row = session.execute(text("SELECT ssn_last4, date_of_birth FROM identity_verifications")).one()
    assert all(str(v).startswith("gAAAAA") for v in row)
    session.expire_all()
    i = session.query(IdentityVerification).one()
    assert i.ssn_last4 == "9876" and i.date_of_birth == date(1970, 1, 2)


def test_fee_rules_bands_caps_and_override(client, session, admin):  # noqa: F811
    upsert(session, "dallas_tx", [RecordIn(
        source_key="F1", state="TX", county="Dallas", sale_type="tax_sale", reference="F1", owner_name="Fay Fee",
        owner_address="", amount_cents=8_000_000, sale_date=date(2025, 3, 1), source_url="")], full_snapshot=True)
    h = signup(client, "fay@example.com", "Fay Fee")
    verify_identity(client, h, "Fay Fee")
    [m] = client.get("/me/matches", headers=h).json()["matches"]
    assert m["fee_pct"] == 15.0  # default 15% and the $50k-$100k band (15%)

    client.post("/admin/fees/rules", headers=admin, json={"state": "TX", "county": "Dallas County", "base_pct": 30,
                                                          "legal_max_pct": 20, "legal_source": "test cap"})
    quote = client.get(f"/admin/fees/quote?record_id={m['record_id']}", headers=admin).json()
    assert quote["average_pct"] == 22.5 and quote["final_pct"] == 20 and quote["county_pct_from"] == "county"
    claim = client.post("/me/claims", headers=h, json={"record_id": m["record_id"]}).json()
    assert claim["fee_pct"] == 20

    assert client.post(f"/admin/claims/{claim['id']}/fee", headers=admin, json={"fee_pct": 25}).status_code == 422
    r = client.post(f"/admin/claims/{claim['id']}/fee", headers=admin, json={"fee_pct": 12, "note": "hardship"})
    assert r.status_code == 200 and r.json()["fee_basis"]["override"] is True
    assert client.get(f"/me/claims/{claim['id']}/agreement", headers=h).json()["fee_pct"] == 12
    assert client.get("/admin/fees", headers=admin).json()["bands"][-1]["up_to_cents"] is None


def test_family_member_claim(client, session, admin):  # noqa: F811
    upsert(session, "dallas_tx", [RecordIn(
        source_key="H1", state="TX", county="Dallas", sale_type="tax_sale", reference="H1",
        owner_name="Mary Parent", owner_address="77 Oak Ln, Dallas, TX", amount_cents=3_000_000,
        sale_date=date(2025, 2, 1), source_url="")], full_snapshot=True)
    h = signup(client, "kid@example.com", "Sam Child")
    body = {"full_name": "Mary Parent", "relationship": "parent", "basis": "heir", "date_of_death": "2025-05-01",
            "death_certificate_b64": TEST_JPEG, "relationship_proof_b64": TEST_JPEG, "addresses": [ADDRESS],
            "consent": True}
    assert client.post("/me/relatives", headers=h, json=body).status_code == 403  # own ID first
    verify_identity(client, h, "Sam Child")
    assert client.post("/me/relatives", headers=h, json={**body, "death_certificate_b64": None}).status_code == 422
    rel = client.post("/me/relatives", headers=h, json=body).json()
    assert rel["review_status"] == "pending" and rel["addresses"][0]["street"] == "77 Oak Ln"
    assert client.get("/me", headers=h).json()["addresses"] == []  # relative's homes aren't the user's
    assert client.get("/me/matches", headers=h).json()["matches"] == []  # hidden until approved

    [pending] = client.get("/admin/relatives", headers=admin).json()
    assert pending["possible_matches"] == 1 and "death_certificate" in pending["documents"]
    client.post(f"/admin/relatives/{rel['id']}", headers=admin, json={"decision": "approved"})
    [m] = client.get("/me/matches", headers=h).json()["matches"]
    assert m["on_behalf_of"].startswith("Mary Parent (your parent") and m["confidence"] == "strong"
    claim = client.post("/me/claims", headers=h, json={"record_id": m["record_id"]}).json()
    assert claim["on_behalf_of"] == m["on_behalf_of"]
    text_ = client.get(f"/me/claims/{claim['id']}/agreement", headers=h).json()["text"]
    assert "as an heir of Mary Parent" in text_


def test_deadlines_and_legal_text(client, session):
    upsert(session, "dallas_tx", [RecordIn(
        source_key="D1", state="TX", county="Dallas", sale_type="tax_sale", reference="D1", owner_name="Dee Line",
        owner_address="", amount_cents=500_000, sale_date=date(2025, 1, 7), source_url="")], full_snapshot=True)
    h = signup(client, "dee@example.com", "Dee Line")
    verify_identity(client, h, "Dee Line")
    [m] = client.get("/me/matches", headers=h).json()["matches"]
    assert m["deadline_date"] == "2027-01-07"
    assert "taxing units" in m["legal"]["if_missed"] and "not a law firm" in m["legal"]["facilitator"]
    assert "heir" in m["legal"]["family_proof"]
    p = client.get("/policies").json()
    assert "Digital Personal Data Protection Act" in p["privacy"] and "not a law firm" in p["terms"]


def test_privacy_export_and_delete(client, session, admin):  # noqa: F811
    h = signup(client, "gone@example.com", "Gone Person")
    assert client.get("/me", headers=h).json()["terms_current"] is True
    data = client.get("/me/export", headers=h).json()
    assert data["account"]["email"] == "gone@example.com"
    assert {c["kind"] for c in data["consents"]} == {"terms", "privacy"}
    assert any(a["action"] == "account.created" for a in data["activity"])
    r = client.post("/me/delete", headers=h).json()
    assert r["deleted"] is True
    assert client.get("/me", headers=h).status_code == 401

    # With a signed agreement, the account is closed and kept for the retention period
    ch, claim = claimant_with_claim(client, session)
    r = client.post("/me/delete", headers=ch).json()
    assert r["deleted"] is False and "7 years" in r["message"]
    assert client.get("/me", headers=ch).status_code == 401  # signed out everywhere
    assert [d["email"] for d in client.get("/admin/deletion-requests", headers=admin).json()] == ["jane@example.com"]


def test_security_controls(client):
    h = signup(client, "sec@example.com", "Sec Person")
    r = client.get("/health")
    assert r.headers["x-frame-options"] == "DENY" and "max-age" in r.headers["strict-transport-security"]

    assert client.post("/auth/logout-all", headers=h).status_code == 200
    assert client.get("/me", headers=h).status_code == 401  # old token retired

    for _ in range(8):
        assert client.post("/auth/login", json={"email": "sec@example.com", "password": "wrong"}).status_code == 401
    r = client.post("/auth/login", json={"email": "sec@example.com", "password": "correct horse"})
    assert r.status_code == 429

    no_terms = client.post("/auth/signup", json={"email": "n@example.com", "password": "correct horse",
                                                 "full_name": "No Terms"})
    assert no_terms.status_code == 422 and "Terms" in no_terms.text


def test_signature_evidence_for_staff(client, session, admin):  # noqa: F811
    ch, claim = claimant_with_claim(client, session)
    ev = client.get(f"/admin/claims/{claim['id']}/evidence", headers=admin).json()
    assert ev["text_unchanged"] and ev["name_matches_id"] and ev["audit_chain"]["ok"]
    assert any(t["action"] == "agreement.signed" for t in ev["trail"])
    sig = client.get(f"/admin/claims/{claim['id']}/signature", headers=admin)
    assert sig.status_code == 200 and sig.content == base64.b64decode(
        __import__("tests.conftest", fromlist=["SIGNATURE_PNG"]).SIGNATURE_PNG)


def test_demo_attorney_login(client, monkeypatch):
    from surpay import config
    monkeypatch.setattr(config, "DEMO_ENABLED", True)
    for _ in range(2):  # resets cleanly each time
        r = client.post("/auth/demo-attorney")
        assert r.status_code == 200 and r.json()["user"]["role"] == "attorney"
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert client.get("/attorney/me", headers=h).json()["status"] == "approved"
        [case] = client.get("/attorney/cases", headers=h).json()
        assert case["assignment_status"] == "offered" and case["county"] == "Demo" and case["status"] == "identity_verified"
    case = client.post(f"/attorney/cases/{case['id']}/accept", headers=h, json={"conflict_checked": True}).json()
    assert case["claimant"]["name"] == "Casey Placeholder" and case["agreement"]["has_signature_image"]
    assert client.get(f"/attorney/cases/{case['id']}/packet", headers=h).content.startswith(b"%PDF")
    monkeypatch.setattr(config, "DEMO_ENABLED", False)
    assert client.post("/auth/demo-attorney").status_code == 404
