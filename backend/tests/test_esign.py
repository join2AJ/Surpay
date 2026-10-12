"""Two-factor signing, forms filled in the app (W-9, affidavit), and the signed-document registry."""

import io

from pypdf import PdfReader

from tests.conftest import SIGNATURE_PNG, two_factor
from tests.test_attorneys import admin, attorney, claimant_with_claim, signup  # noqa: F401  (fixture)

TZ = {"X-Time-Zone": "America/New_York"}


def accepted(client, session, admin):  # noqa: F811
    ah, auid = attorney(client, admin, "alex@law.com", "Alex Counsel", ["Dallas County"])
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"})
    ch, claim = claimant_with_claim(client, session)
    client.post(f"/attorney/cases/{claim['id']}/accept", headers=ah, json={"conflict_checked": True})
    return ah, ch, claim


def test_codes_are_checked(client):
    h = signup(client, "jane@example.com", "Jane Sample")
    assert client.get("/me/verify", headers=h).json()["ready_to_sign"] is False
    sent = client.post("/me/verify/start", headers=h, json={"channel": "email"}).json()
    assert sent["sent_to"] == "j•••@example.com" and len(sent["test_code"]) == 6
    assert client.post("/me/verify/confirm", headers=h, json={"channel": "email", "code": "000000"}).status_code == 422
    ok = client.post("/me/verify/confirm", headers=h, json={"channel": "email", "code": sent["test_code"]}).json()
    assert ok["email"]["fresh"] and not ok["ready_to_sign"]
    # No phone yet: the user is told to add one
    assert client.post("/me/verify/start", headers=h, json={"channel": "phone"}).status_code in (200, 409)


def test_signing_needs_both_codes(client, session):
    from surpay.ingest import upsert
    from surpay.scrapers.base import RecordIn
    from datetime import date
    from tests.conftest import verify_identity
    upsert(session, "dallas_tx", [RecordIn(
        source_key="TX-1", state="TX", county="Dallas", sale_type="tax_sale", reference="Case TX-21-0001",
        owner_name="Jane Sample", owner_address="", amount_cents=2_000_000, sale_date=date(2025, 1, 7),
        source_url="")], full_snapshot=True)
    h = signup(client, "jane@example.com", "Jane Sample")
    verify_identity(client, h, "Jane Sample")
    rid = client.get("/me/matches", headers=h).json()["matches"][0]["record_id"]
    claim = client.post("/me/claims", headers=h, json={"record_id": rid}).json()
    body = {"signature_name": "Jane Sample", "agreed": True, "signature_png_b64": SIGNATURE_PNG}
    r = client.post(f"/me/claims/{claim['id']}/agreement", headers=h, json=body)
    assert r.status_code == 403 and "codes" in r.text
    two_factor(client, h)
    signed = client.post(f"/me/claims/{claim['id']}/agreement", headers={**h, **TZ}, json=body).json()
    assert signed["status"] == "identity_verified"
    a = client.get(f"/me/claims/{claim['id']}/agreement", headers=h).json()
    assert a["doc_id"] == a["document_sha256"][:16] and ("EDT" in a["signed_at_display"] or "EST" in a["signed_at_display"])
    assert "UTC" in a["signed_at_display"]
    [doc] = client.get("/me/documents", headers=h).json()
    assert doc["kind"] == "agreement" and doc["two_factor"] is True
    assert client.get(f"/me/documents/{doc['doc_id']}/pdf", headers=h).content.startswith(b"%PDF")


def test_w9_and_affidavit_signed_in_app(client, session, admin):  # noqa: F811
    ah, ch, claim = accepted(client, session, admin)
    kinds = {r["kind"]: r for r in client.get(f"/me/claims/{claim['id']}", headers=ch).json()["document_requests"]}
    assert kinds["w9"]["fill_in_app"] and kinds["w9"]["source"] == "checklist"
    pre = client.get(f"/me/claims/{claim['id']}/forms/w9", headers=ch).json()
    assert pre["fields"]["name"] == "Jane Sample" and "SP-" in pre["fields"]["account_numbers"]

    form = {"fields": {"ssn": "987-65-1234", "address": "1 Main St", "city_state_zip": "Dallas, TX 75201"},
            "signature_png_b64": SIGNATURE_PNG, "certify": True}
    two_factor(client, ch)
    bad = client.post(f"/me/claims/{claim['id']}/forms/w9", headers=ch,
                      json={**form, "fields": {**form["fields"], "ssn": "987-65-0000"}})
    assert bad.status_code == 422 and "last 4" in bad.text  # must match the last 4 given at ID check
    r = client.post(f"/me/claims/{claim['id']}/forms/w9", headers={**ch, **TZ}, json=form).json()
    doc = r["document"]
    assert doc["kind"] == "w9" and len(doc["doc_id"]) == 16 and doc["two_factor"]
    w9 = [x for x in r["claim"]["document_requests"] if x["kind"] == "w9"][0]
    assert w9["status"] == "uploaded" and w9["doc_id"] == doc["doc_id"]

    # The attorney gets the filled-in official form, and a notification
    f = client.get(f"/attorney/cases/{claim['id']}/document-requests/{w9['id']}/file", headers=ah)
    assert f.headers["content-type"] == "application/pdf"
    fields = PdfReader(io.BytesIO(f.content)).get_fields()
    values = {k.split(".")[-1]: v.get("/V") for k, v in fields.items()}
    assert values["f1_01[0]"] == "Jane Sample" and values["f1_13[0]"] == "1234"
    assert any(n["title"].startswith("Client uploaded: IRS Form W-9")
               for n in client.get("/me/notifications", headers=ah).json()["items"])

    aff = client.post(f"/me/claims/{claim['id']}/forms/ownership_affidavit", headers=ch,
                      json={"fields": {"liens": "none"}, "signature_png_b64": SIGNATURE_PNG, "certify": True}).json()
    assert aff["document"]["title"].startswith("Affidavit")
    packet = client.get(f"/attorney/cases/{claim['id']}/packet", headers=ah).content
    assert len(PdfReader(io.BytesIO(packet)).pages) >= 6  # packet + W-9 (2 pages) + affidavit (2+ pages)

    # Staff find any signed document by its fingerprint, with the evidence (SSN masked)
    found = client.get(f"/admin/documents/{doc['doc_id']}", headers=admin).json()
    assert found["signer_name"] == "Jane Sample" and found["data"]["ssn"] == "•••-••-1234"
    assert found["email_verified_at"] and found["phone_verified_at"] and found["audit_id"]
    assert client.get(f"/admin/documents/{doc['doc_id']}/pdf", headers=admin).content.startswith(b"%PDF")


def test_attorney_sends_a_document_back(client, session, admin):  # noqa: F811
    ah, ch, claim = accepted(client, session, admin)
    two_factor(client, ch)
    r = client.post(f"/me/claims/{claim['id']}/forms/w9", headers=ch, json={
        "fields": {"ssn": "987651234", "address": "1 Main St", "city_state_zip": "Dallas, TX 75201"},
        "signature_png_b64": SIGNATURE_PNG, "certify": True}).json()
    w9 = [x for x in r["claim"]["document_requests"] if x["kind"] == "w9"][0]
    case = client.post(f"/attorney/cases/{claim['id']}/document-requests/{w9['id']}/review", headers=ah,
                       json={"decision": "rejected", "note": "The county needs this signed in front of a notary."}).json()
    assert [x for x in case["document_requests"] if x["kind"] == "w9"][0]["status"] == "rejected"
    titles = [n["title"] for n in client.get("/me/notifications", headers=ch).json()["items"]]
    assert "Please upload again: IRS Form W-9" in titles


def test_activity_log_and_app_number(client, session, admin):  # noqa: F811
    ah, ch, claim = accepted(client, session, admin)
    me = client.get("/me", headers=ch).json()
    assert me["app_number"] == f"SU-{100000 + me['id']}"
    log = client.get("/me/activity", headers=ch).json()
    labels = [e["label"] for e in log]
    assert "Signed the claim agreement" in labels and "Started a claim" in labels
    accepted_by_attorney = [e for e in log if e["action"] == "case.accepted"][0]
    assert accepted_by_attorney["ip"] == "" and accepted_by_attorney["device_info"] == "Your attorney"
    assert client.get("/me/activity", headers=ah).json()[0]["mine"] is True
