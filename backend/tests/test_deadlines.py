"""The legal clock: days left to claim, colour-coded, on every screen; reminders; no claims after it."""

from datetime import date

from surpay.ingest import upsert
from surpay.legal import deadline_info
from surpay.maintenance import deadline_reminders
from surpay.models import Notification
from surpay.scrapers.base import RecordIn
from tests.conftest import verify_identity
from tests.test_attorneys import admin, attorney, claimant_with_claim, signup  # noqa: F401  (fixture)

TODAY = date(2026, 10, 11)


def test_urgency_levels():
    clock = lambda sale, status=None: deadline_info("TX", sale, status, as_of=TODAY)  # noqa: E731
    safe = clock(date(2025, 8, 1))
    assert safe["urgency"] == "safe" and safe["days_left"] == 294 and safe["label"] == "294 days left"
    assert safe["file_by"] == date(2027, 6, 17) and 0 < safe["elapsed_pct"] < 100
    assert clock(date(2025, 1, 7))["urgency"] == "soon"           # 88 days
    urgent = clock(date(2024, 11, 1))
    assert urgent["urgency"] == "urgent" and urgent["days_left"] == 21 and "Only 21 days left" in urgent["message"]
    assert clock(date(2024, 10, 11))["label"] == "Last day to claim"
    gone = clock(date(2024, 1, 1))
    assert gone["urgency"] == "expired" and not gone["can_claim"] and "taxing units" in gone["message"]
    assert clock(date(2024, 1, 1), "filed")["urgency"] == "met"   # filed in time: the clock stops
    assert deadline_info("TX", None, as_of=TODAY)["urgency"] == "unknown"
    assert deadline_info("ZZ", date(2025, 1, 1), as_of=TODAY)["urgency"] == "unknown"


def test_every_screen_shows_the_clock(client, session, admin):  # noqa: F811
    ah, auid = attorney(client, admin, "alex@law.com", "Alex Counsel", ["Dallas County"])
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"})
    ch, claim = claimant_with_claim(client, session)
    assert claim["deadline"]["urgency"] == "soon" and claim["deadline"]["days_left"] == 88
    match = client.get("/me/matches", headers=ch).json()["matches"][0]
    assert match["deadline"]["label"] == "88 days left" and match["deadline"]["color"].startswith("#")
    case = client.get("/attorney/cases", headers=ah).json()[0]
    assert case["deadline"]["days_left"] == 88
    o = client.get("/admin/overview", headers=admin).json()
    assert o["records"]["deadlines"]["soon"] == {"records": 1, "total_cents": 2_000_000}
    assert o["records"]["deadlines"]["next_90_days"]["records"] == 1
    rows = client.get("/admin/records?urgency=soon&sort=deadline", headers=admin).json()
    assert rows["total"] == 1 and rows["records"][0]["days_left"] == 88
    assert client.get("/admin/records?urgency=urgent", headers=admin).json()["total"] == 0
    assert "88 days left" in client.get("/admin/claims.csv", headers=admin).text

    # Once filed, the deadline is met
    client.post(f"/attorney/cases/{claim['id']}/accept", headers=ah, json={"conflict_checked": True})
    client.post(f"/attorney/cases/{claim['id']}/status", headers=ah, json={"status": "filed", "note": ""})
    assert client.get(f"/me/claims/{claim['id']}", headers=ch).json()["deadline"]["urgency"] == "met"


def test_no_new_claims_after_the_deadline(client, session):
    upsert(session, "dallas_tx", [RecordIn(
        source_key="OLD", state="TX", county="Dallas", sale_type="tax_sale", reference="Case TX-19-0001",
        owner_name="Jane Sample", owner_address="", amount_cents=500_000, sale_date=date(2023, 3, 1),
        source_url="https://example/list.pdf")], full_snapshot=True)
    h = signup(client, "jane@example.com", "Jane Sample")
    verify_identity(client, h, "Jane Sample")
    [m] = client.get("/me/matches", headers=h).json()["matches"]
    assert m["deadline"]["urgency"] == "expired" and not m["deadline"]["can_claim"]
    r = client.post("/me/claims", headers=h, json={"record_id": m["record_id"]})
    assert r.status_code == 409 and "passed" in r.json()["detail"]


def test_reminders_once_per_milestone(client, session, admin):  # noqa: F811
    ah, auid = attorney(client, admin, "alex@law.com", "Alex Counsel", ["Dallas County"])
    client.post(f"/admin/attorneys/{auid}", headers=admin, json={"decision": "approved"})
    ch, claim = claimant_with_claim(client, session)
    client.post(f"/attorney/cases/{claim['id']}/accept", headers=ah, json={"conflict_checked": True})
    session.expire_all()
    assert deadline_reminders(session, TODAY) == 2          # claimant + attorney, the 90-day milestone
    assert deadline_reminders(session, TODAY) == 0          # not again
    assert deadline_reminders(session, date(2026, 12, 10)) == 2  # 28 days left: the 30-day milestone
    session.commit()
    kinds = sorted(n.kind for n in session.query(Notification).filter(Notification.kind.like("deadline_%")))
    assert kinds == ["deadline_30", "deadline_30", "deadline_90", "deadline_90"]
    titles = [n["title"] for n in client.get("/me/notifications", headers=ch).json()["items"]]
    assert any("days left to claim $20,000.00" in t for t in titles)


def test_reminder_for_money_not_yet_claimed(client, session):
    upsert(session, "dallas_tx", [RecordIn(
        source_key="TX-9", state="TX", county="Dallas", sale_type="tax_sale", reference="Case TX-21-0009",
        owner_name="Jane Sample", owner_address="", amount_cents=900_000, sale_date=date(2024, 11, 1),
        source_url="https://example/list.pdf")], full_snapshot=True)
    h = signup(client, "jane@example.com", "Jane Sample")
    verify_identity(client, h, "Jane Sample")
    session.expire_all()
    assert deadline_reminders(session, TODAY) == 1
    assert deadline_reminders(session, TODAY) == 0
    session.commit()
    [n] = [n for n in client.get("/me/notifications", headers=h).json()["items"] if n["title"].startswith("21 days")]
    assert "haven't started" in n["body"]
