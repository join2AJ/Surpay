"""The one-tap admin demo sees and acts only on demo data; real people's records stay hidden."""

import pytest

from surpay import config
from tests.conftest import verify_identity
from tests.test_attorneys import apply, claimant_with_claim, signup


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(config, "DEMO_ENABLED", True)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "real-staff-token")


def demo_admin(client):
    r = client.post("/auth/demo-admin")
    assert r.status_code == 200, r.text
    return {"X-Admin-Token": r.json()["token"]}


def test_demo_admin_is_off_without_demo_mode(client, monkeypatch):
    monkeypatch.setattr(config, "DEMO_ENABLED", False)
    assert client.post("/auth/demo-admin").status_code == 404


def test_demo_admin_sees_only_demo_data(client, session, demo):
    # Real activity: a verified claimant with a Dallas claim, a pending real ID, a Dallas attorney
    real_h, real_claim = claimant_with_claim(client, session)
    pending = signup(client, "pending@example.com", "Penny Pending")
    verify_identity(client, pending, "Penny Pending", approve=False)
    real_lawyer = signup(client, "dallas@law.com", "Dal Lawyer", role="attorney")
    apply(client, real_lawyer, ["Dallas County"])
    # Demo activity: the demo attorney's case, and a tester applying for Demo County only
    client.post("/auth/demo-attorney")
    tester = signup(client, "tester@law.com", "Tess Tester", role="attorney")
    apply(client, tester, ["Demo County"], state="OH")

    h = demo_admin(client)
    assert client.get("/admin/whoami", headers=h).json() == {"demo": True}
    claims = client.get("/admin/claims", headers=h).json()
    assert {c["county"] for c in claims} == {"Demo"} and claims[0]["user"]["email"] == "client-demo@surpay.test"
    assert client.get("/admin/identities", headers=h).json() == []  # Penny's real ID is hidden
    assert [a["email"] for a in client.get("/admin/attorneys", headers=h).json()] == ["tester@law.com"]

    # It can't reach or change real records
    uid = client.get("/me", headers=pending).json()["id"]
    assert client.get(f"/admin/users/{uid}/documents/selfie", headers=h).status_code == 404
    r = client.post(f"/admin/users/{uid}/identity", headers=h, json={"decision": "approved"})
    assert r.status_code == 404  # approving a real ID would unlock real records
    assert client.post(f"/admin/claims/{real_claim['id']}/status", headers=h,
                       json={"status": "filed"}).status_code == 404
    assert client.post("/admin/fees/rules", headers=h, json={"state": "OH", "base_pct": 10}).status_code == 403

    # ...but it can run the demo end to end: approve the Demo County attorney, move a demo claim
    tid = client.get("/me", headers=tester).json()["id"]
    assert client.post(f"/admin/attorneys/{tid}", headers=h, json={"decision": "approved"}).status_code == 200
    demo_claim = claims[0]["id"]
    assert client.post(f"/admin/claims/{demo_claim}/status", headers=h, json={"status": "filed"}).status_code == 200

    # Real staff still see everything
    staff = {"X-Admin-Token": "real-staff-token"}
    assert client.get("/admin/whoami", headers=staff).json() == {"demo": False}
    assert {c["county"] for c in client.get("/admin/claims", headers=staff).json()} == {"Demo", "Dallas"}
    assert len(client.get("/admin/identities", headers=staff).json()) == 1


def test_tester_claiming_a_demo_record_stays_private(client, session, demo):
    client.post("/auth/demo")  # loads the demo records
    h = signup(client, "real.tester@example.com", "Jordan Testwell")
    verify_identity(client, h, "Jordan Testwell")
    rid = client.get("/me/matches", headers=h).json()["matches"][0]["record_id"]
    client.post("/me/claims", headers=h, json={"record_id": rid})
    [c] = client.get("/admin/claims", headers=demo_admin(client)).json()
    assert c["identity"] is None and "hidden" in c["user"]["email"]
    assert client.get(f"/admin/claims/{c['id']}/messages", headers=demo_admin(client)).status_code == 404


def test_wrong_or_expired_pass_is_refused(client, demo):
    assert client.get("/admin/claims", headers={"X-Admin-Token": "nonsense"}).status_code == 401
    import jwt
    from datetime import datetime, timedelta, timezone
    old = jwt.encode({"scope": "demo_admin", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                     config.SECRET_KEY, algorithm="HS256")
    assert client.get("/admin/claims", headers={"X-Admin-Token": old}).status_code == 401
