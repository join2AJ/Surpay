"""Regression tests for the v0.3 audit: authorization, state machine, privacy and legal controls."""

import base64
import io
from datetime import date, datetime, timedelta, timezone

from PIL import Image

from surpay import crypto
from surpay.ingest import upsert
from surpay.models import AuditLog, Claim, IdentityVerification, User
from surpay.scrapers.base import RecordIn
from tests.conftest import SIGNATURE_PNG, TEST_JPEG, verify_identity
from tests.test_attorneys import admin, attorney, claimant_with_claim, signup  # noqa: F401  (fixture)

ACCEPT = {"conflict_checked": True}


def accepted_case(client, session, admin, email="alex@law.com"):  # noqa: F811
    ah, auid = attorney(client, admin, email, "Alex Counsel", ["Dallas County"])
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"})
    ch, claim = claimant_with_claim(client, session)
    [case] = client.get("/attorney/cases", headers=ah).json()
    return ah, auid, ch, claim, case


def test_accept_requires_conflict_check_and_stages_cannot_be_skipped(client, session, admin):  # noqa: F811
    ah, _, ch, claim, case = accepted_case(client, session, admin)
    r = client.post(f"/attorney/cases/{case['id']}/accept", headers=ah, json={})
    assert r.status_code == 422 and "conflict" in r.text
    assert client.post(f"/attorney/cases/{case['id']}/accept", headers=ah, json=ACCEPT).status_code == 200

    # Straight to "paid" (which would make the attorney's fee due) is refused
    r = client.post(f"/attorney/cases/{case['id']}/status", headers=ah, json={"status": "paid"})
    assert r.status_code == 409
    assert client.get(f"/me/claims/{claim['id']}", headers=ch).json()["status"] == "attorney_assigned"
    for s in ("filed", "approved"):
        assert client.post(f"/attorney/cases/{case['id']}/status", headers=ah, json={"status": s}).status_code == 200
    # ...and going backwards too
    assert client.post(f"/attorney/cases/{case['id']}/status", headers=ah, json={"status": "filed"}).status_code == 409
    assert client.post(f"/attorney/cases/{case['id']}/status", headers=ah, json={"status": "paid"}).status_code == 200


def test_withdrawn_case_is_closed_to_the_attorney(client, session, admin):  # noqa: F811
    ah, _, ch, claim, case = accepted_case(client, session, admin)
    client.post(f"/admin/claims/{claim['id']}/status", headers=admin, json={"status": "withdrawn", "note": "client wrote in"})
    assert client.post(f"/attorney/cases/{case['id']}/accept", headers=ah, json=ACCEPT).status_code == 404
    assert client.get(f"/attorney/cases/{case['id']}/documents/selfie", headers=ah).status_code == 404
    assert client.get("/attorney/cases", headers=ah).json() == []


def test_claimant_cannot_withdraw_in_app(client, session):
    ch, claim = claimant_with_claim(client, session)
    assert client.post(f"/me/claims/{claim['id']}/withdraw", headers=ch).status_code in (404, 405)


def test_new_attorney_does_not_see_previous_conversation(client, session, admin):  # noqa: F811
    ah, _, ch, claim, case = accepted_case(client, session, admin)
    client.post(f"/attorney/cases/{case['id']}/accept", headers=ah, json=ACCEPT)
    client.post(f"/attorney/cases/{case['id']}/messages", headers=ah, json={"body": "Private note to Jane"})
    bh, buid = attorney(client, admin, "bea@law.com", "Bea Barrister", ["Dallas County"])
    client.post(f"/admin/attorneys/{buid}", headers=admin, json={"decision": "approved"})

    # The client asks for a different attorney (their right before filing)
    c = client.post(f"/me/claims/{claim['id']}/change-attorney", headers=ch).json()
    assert c["attorney"] is None and c["status"] == "identity_verified"
    titles = [n["title"] for n in client.get("/me/notifications", headers=ch).json()["items"]]
    assert "We're finding you a new attorney" in titles

    [new_case] = client.get("/attorney/cases", headers=bh).json()
    client.post(f"/attorney/cases/{new_case['id']}/accept", headers=bh, json=ACCEPT)
    assert client.get(f"/attorney/cases/{new_case['id']}/messages", headers=bh).json()["messages"] == []
    # and the client can't message the new attorney until they write first
    chat = client.get(f"/me/claims/{claim['id']}/messages", headers=ch).json()
    assert chat["messages"] == [] and not chat["can_send"]


def test_suspending_an_attorney_reassigns_their_cases(client, session, admin):  # noqa: F811
    ah, auid, ch, claim, case = accepted_case(client, session, admin)
    client.post(f"/attorney/cases/{case['id']}/accept", headers=ah, json=ACCEPT)
    bh, buid = attorney(client, admin, "bea@law.com", "Bea Barrister", ["Dallas County"])
    client.post(f"/admin/attorneys/{buid}", headers=admin, json={"decision": "approved"})
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "rejected", "note": "license lapsed"})
    [moved] = client.get("/attorney/cases", headers=bh).json()
    assert moved["id"] == case["id"] and moved["assignment_status"] == "offered"


def test_id_rejected_after_signing_still_reaches_an_attorney(client, session, admin):  # noqa: F811
    upsert(session, "dallas_tx", [RecordIn(
        source_key="R1", state="TX", county="Dallas", sale_type="tax_sale", reference="R1", owner_name="Rae Retry",
        owner_address="", amount_cents=900_000, sale_date=date(2025, 3, 1), source_url="")], full_snapshot=True)
    h = signup(client, "rae@example.com", "Rae Retry")
    verify_identity(client, h, "Rae Retry")
    rid = client.get("/me/matches", headers=h).json()["matches"][0]["record_id"]
    claim = client.post("/me/claims", headers=h, json={"record_id": rid}).json()
    # Pretend the approval is undone (e.g. a second look finds a blurry ID) after signing
    uid = client.get("/me", headers=h).json()["id"]
    with __import__("surpay.db", fromlist=["SessionLocal"]).SessionLocal() as s:
        s.get(User, uid).identity.review_status = "pending"
        s.commit()
    client.post(f"/me/claims/{claim['id']}/agreement", headers=h,
                json={"signature_name": "Rae Retry", "agreed": True, "signature_png_b64": SIGNATURE_PNG})
    client.post(f"/admin/users/{uid}/identity", headers=admin, json={"decision": "rejected", "note": "blurry"})
    resubmit = {"legal_name": "Rae Retry", "date_of_birth": "1980-04-02", "ssn_last4": "1234", "phone": "555-010-0000",
                "street": "9 New Home Ln", "city": "Columbus", "state": "OH", "zip": "43004",
                "id_type": "drivers_license", "id_front_b64": TEST_JPEG, "selfie_b64": TEST_JPEG, "consent": True}
    assert client.post("/me/identity", headers=h, json=resubmit).status_code == 200
    assert client.get(f"/me/claims/{claim['id']}", headers=h).json()["status"] == "agreement_signed"
    client.post(f"/admin/users/{uid}/identity", headers=admin, json={"decision": "approved"})
    assert client.get(f"/me/claims/{claim['id']}", headers=h).json()["status"] == "identity_verified"


def test_closed_accounts_and_passwords(client, session):
    weak = client.post("/auth/signup", json={"email": "w@example.com", "password": "password123",
                                             "full_name": "Weak Pass", "accept_terms": True})
    assert weak.status_code == 422 and "too easy" in weak.text

    h = signup(client, "pat@example.com", "Pat Change")
    r = client.post("/auth/change-password", headers=h, json={"current_password": "wrong", "new_password": "a new long secret"})
    assert r.status_code == 403
    r = client.post("/auth/change-password", headers=h,
                    json={"current_password": "correct horse", "new_password": "a new long secret"})
    assert r.status_code == 200
    assert client.get("/me", headers=h).status_code == 401  # other sessions signed out
    assert client.post("/auth/login", json={"email": "pat@example.com", "password": "a new long secret"}).status_code == 200

    # An attorney who worked a case keeps the record; the closed account can't sign in again
    ch, claim = claimant_with_claim(client, session)
    assert client.post("/me/delete", headers=ch).json()["deleted"] is False
    r = client.post("/auth/login", json={"email": "jane@example.com", "password": "correct horse"})
    assert r.status_code == 403 and "closed" in r.text


def test_spoofed_forwarded_for_is_ignored(client):
    client.post("/auth/signup", headers={"X-Forwarded-For": "6.6.6.6, 203.0.113.9, 10.0.0.7"},
                json={"email": "ip@example.com", "password": "correct horse", "full_name": "Ip Person",
                      "accept_terms": True})
    from surpay.db import SessionLocal
    with SessionLocal() as s:
        entry = s.query(AuditLog).filter_by(action="account.created").one()
        assert entry.ip_address == "203.0.113.9"  # what Render's edge saw, not the forged or internal hop


def test_photo_metadata_is_stripped(client, session):
    img = Image.new("RGB", (80, 60), (10, 120, 90))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # camera make
    exif[0x0110] = "Model SN-12345"  # device model / serial
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    assert b"PhoneMaker" in out.getvalue()
    h = signup(client, "gps@example.com", "Gee Pees")
    body = {"legal_name": "Gee Pees", "date_of_birth": "1980-04-02", "ssn_last4": "1234", "phone": "555-010-0000",
            "street": "9 New Home Ln", "city": "Columbus", "state": "OH", "zip": "43004", "id_type": "drivers_license",
            "id_front_b64": base64.b64encode(out.getvalue()).decode(), "selfie_b64": TEST_JPEG, "consent": True}
    assert client.post("/me/identity", headers=h, json=body).status_code == 200
    stored = crypto.decrypt(session.query(IdentityVerification).one().id_front)
    assert b"PhoneMaker" not in stored and len(Image.open(io.BytesIO(stored)).getexif()) == 0
    # A file that only pretends to be a JPEG is refused
    import pytest
    from fastapi import HTTPException

    from surpay.deps import encrypt_image
    with pytest.raises(HTTPException) as e:
        encrypt_image(base64.b64encode(b"\xff\xd8\xff\xe0" + b"<script>" * 40).decode(), "ID front")
    assert e.value.status_code == 422


def test_outdated_terms_block_new_actions(client, session, monkeypatch):
    h = signup(client, "terms@example.com", "Tess Terms")
    verify_identity(client, h, "Tess Terms")
    from surpay import me_api
    monkeypatch.setattr(me_api, "TERMS_VERSION", "terms-2099-01")
    assert client.get("/me", headers=h).json()["terms_current"] is False
    r = client.post("/me/claims", headers=h, json={"record_id": 1})
    assert r.status_code == 403 and "Terms" in r.text
    client.post("/me/consents/accept-current", headers=h)
    assert client.get("/me", headers=h).json()["terms_current"] is True


def test_duplicate_identity_flagged_for_staff(client, admin):  # noqa: F811
    for email in ("one@example.com", "two@example.com"):
        h = signup(client, email, "Dee Double")
        verify_identity(client, h, "Dee Double", approve=False)
    pending = client.get("/admin/identities", headers=admin).json()
    assert {p["user"]["email"]: p["possible_duplicates"] for p in pending} == {
        "one@example.com": ["two@example.com"], "two@example.com": ["one@example.com"]}


def test_daily_purge(client, session, admin):  # noqa: F811
    from surpay.maintenance import purge

    signup(client, "ghost@example.com", "Gus Ghost")
    ah, _, ch, claim, case = accepted_case(client, session, admin)
    session.expire_all()
    later = datetime.now(timezone.utc) + timedelta(days=200)
    result = purge(session, now=later)
    assert result["erased_accounts"] == 1  # the never-verified account only
    assert session.query(User).filter_by(email="ghost@example.com").first() is None
    assert session.query(User).filter_by(email="jane@example.com").first() is not None

    # An offer left unanswered past the deadline goes back to the queue
    c = session.get(Claim, case["id"])
    c.assigned_at = datetime.now(timezone.utc) - timedelta(days=5)
    session.commit()
    assert purge(session)["expired_offers"] == 1
    assert client.get("/attorney/cases", headers=ah).json() == []
