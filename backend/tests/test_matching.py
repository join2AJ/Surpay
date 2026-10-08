from datetime import date

from surpay.ingest import upsert
from surpay.matching import LIKELY, POSSIBLE, STRONG, find_matches
from surpay.models import PreviousAddress, SurplusRecord, User
from surpay.normalize import name_tokens, normalize_street
from surpay.scrapers.base import RecordIn


def rec(key, name, address="", amount=100000, state="OH"):
    return RecordIn(source_key=key, state=state, county="Adams", sale_type="tax_sale",
                    reference=f"Parcel {key}", owner_name=name, owner_address=address,
                    amount_cents=amount, sale_date=date(2024, 6, 17), source_url="u")


def user(session, name, addresses=(), other_names=()):
    u = User(email=f"{name.replace(' ', '.').lower()}@x.com", password_hash="x", full_name=name,
             other_names=list(other_names),
             addresses=[PreviousAddress(street=s, state=st) for s, st in addresses])
    session.add(u)
    session.commit()
    return u


def test_name_tokens():
    assert name_tokens("SMITH, JOHN A. JR") == ["john", "a", "smith"]
    assert name_tokens("John & Mary Smith et al") == ["john", "mary", "smith"]
    assert name_tokens("Estate of Robert O'Neil") == ["robert", "oneil"]


def test_normalize_street():
    assert normalize_street("6063 State Route 73") == normalize_street("6063 St. Rte 73")
    assert normalize_street("12 Oak Lane Apt 4") == "12 oak ln"


def test_confidence_levels(session):
    upsert(session, "t", [
        rec("1", "Robert Sample", "6063 State Route 73, Peebles, OH 45660", 1973260),
        rec("2", "SAMPLE, ROBERT J", "99 Other Rd, Lynx, OH", 500000),
        rec("3", "Robrt Sampel", "", 300000),
        rec("4", "Roberta Simple", "", 200000),
        rec("5", "Robert Sample", "1 Main St, Orlando, FL", 900000, state="FL"),
    ], full_snapshot=True)
    u = user(session, "Robert Sample", addresses=[("6063 St Rte 73", "OH")])
    got = {m.record.source_key: m.confidence for m in find_matches(session, u)}
    assert got["1"] == STRONG
    assert got["2"] == LIKELY
    assert got["5"] == LIKELY  # same name elsewhere: shown, but not confirmed by address
    assert got.get("3") in (POSSIBLE, None)
    assert "4" not in got


def test_joint_owners_and_maiden_name(session):
    upsert(session, "t", [rec("1", "John & Mary Fieldstone", "", 100), rec("2", "Mary Oldname", "", 100)],
           full_snapshot=True)
    u = user(session, "Mary Newname", other_names=["Mary Oldname"])
    keys = {m.record.source_key for m in find_matches(session, u)}
    assert keys == {"2"}
    u2 = user(session, "Mary Fieldstone")
    assert {m.record.source_key for m in find_matches(session, u2)} == {"1"}


def test_delisted_records_are_not_matched(session):
    upsert(session, "t", [rec("1", "Ann Example"), rec("2", "Ann Example")], full_snapshot=True)
    run = upsert(session, "t", [rec("2", "Ann Example")], full_snapshot=True)
    assert run.delisted == 1
    assert session.get(SurplusRecord, 1).status == "delisted"
    u = user(session, "Ann Example")
    assert [m.record.source_key for m in find_matches(session, u)] == ["2"]


def test_upsert_counts_updates(session):
    upsert(session, "t", [rec("1", "Ann Example", amount=100)], full_snapshot=True)
    run = upsert(session, "t", [rec("1", "Ann Example", amount=200)], full_snapshot=True)
    assert (run.added, run.updated) == (0, 1)
    run = upsert(session, "t", [rec("1", "Ann Example", amount=200)], full_snapshot=True)
    assert (run.added, run.updated) == (0, 0)
