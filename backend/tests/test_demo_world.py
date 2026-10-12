"""The shared demo is one connected world: the claimant's signed claim reaches the demo attorney,
the attorney's messages reach the claimant, and signing in again never wipes anyone's progress."""

from tests.conftest import SIGNATURE_PNG


def login(client, path):
    return {"Authorization": f"Bearer {client.post(path).json()['token']}"}


def test_claimant_and_attorney_demos_are_connected(client, monkeypatch):
    from surpay import config
    monkeypatch.setattr(config, "DEMO_ENABLED", True)

    jordan = login(client, "/auth/demo")
    rid = client.get("/me/matches", headers=jordan).json()["matches"][0]["record_id"]
    claim = client.post("/me/claims", headers=jordan, json={"record_id": rid}).json()
    claim = client.post(f"/me/claims/{claim['id']}/agreement", headers=jordan,
                        json={"signature_name": "Jordan Testwell", "agreed": True, "signature_png_b64": SIGNATURE_PNG}).json()
    assert claim["status"] == "identity_verified"

    # The demo attorney gets Jordan's case (alongside Casey's seeded one), with a notification
    avery = login(client, "/auth/demo-attorney")
    cases = {c["id"]: c for c in client.get("/attorney/cases", headers=avery).json()}
    assert claim["id"] in cases and len(cases) == 2
    titles = [n["title"] for n in client.get("/me/notifications", headers=avery).json()["items"]]
    assert "New case offered" in titles
    client.post(f"/attorney/cases/{claim['id']}/accept", headers=avery, json={"conflict_checked": True})
    client.post(f"/attorney/cases/{claim['id']}/messages", headers=avery, json={"body": "Hello Jordan, I have your case."})

    # Jordan signs in again: the claim, the attorney and the message are all there
    jordan = login(client, "/auth/demo")
    mine = client.get(f"/me/claims/{claim['id']}", headers=jordan).json()
    assert mine["status"] == "attorney_assigned" and mine["attorney"]["name"] == "Avery Counsel" and mine["chat_open"]
    msgs = client.get(f"/me/claims/{claim['id']}/messages", headers=jordan).json()["messages"]
    assert msgs[0]["body"] == "Hello Jordan, I have your case."
    client.post(f"/me/claims/{claim['id']}/messages", headers=jordan, json={"body": "Thank you!"})

    # And the attorney's side still shows it accepted, with the reply: no endless re-offer loop
    avery = login(client, "/auth/demo-attorney")
    case = client.get(f"/attorney/cases/{claim['id']}", headers=avery).json()
    assert case["assignment_status"] == "accepted"
    assert [m["body"] for m in client.get(f"/attorney/cases/{claim['id']}/messages", headers=avery).json()["messages"]][-1] == "Thank you!"
    assert len(client.get("/attorney/cases", headers=avery).json()) == 2
