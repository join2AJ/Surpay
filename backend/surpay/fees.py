"""The contingency fee for a case, from three inputs staff maintain in the database:

1. the county's usual rate (a county rule, else the state rule, else DEFAULT_FEE_PCT);
2. the rate for the size of the recovery (fee bands: small amounts carry a higher rate);
3. the most the law allows there (legal_max_pct on the county rule, else the state rule).

The quoted fee is the average of 1 and 2, capped at 3, rounded to the nearest half percent.
Staff can override it for a single case before the agreement is signed.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import Claim, FeeBand, FeeRule, SurplusRecord

DEFAULT_BANDS = [(1_000_000, 25.0), (5_000_000, 20.0), (10_000_000, 15.0), (None, 12.0)]

# Known legal limits, loaded once so staff see them. VERIFY each with counsel before relying on it.
DEFAULT_RULES = [
    {"state": "CO", "legal_max_pct": 0.0,
     "legal_source": "Denver Public Trustee guidance: no fee may be charged to help collect public trustee excess funds",
     "note": "Fees not allowed: tell claimants to claim directly, free."},
    {"state": "IN", "legal_max_pct": 10.0,
     "legal_source": "Indiana Court of Appeals on tax-sale surplus locator fees (10% cap)", "note": "Verify"},
]


def seed_defaults(session: Session) -> None:
    if session.scalar(select(FeeBand.id).limit(1)) is None:
        session.add_all(FeeBand(up_to_cents=up, pct=pct) for up, pct in DEFAULT_BANDS)
    for rule in DEFAULT_RULES:
        exists = session.scalar(select(FeeRule.id).where(FeeRule.state == rule["state"], FeeRule.county == ""))
        if exists is None:
            session.add(FeeRule(county="", **rule))
    session.commit()


def _county_key(county: str) -> str:
    return county.lower().removesuffix(" county").strip()


def _rules(session: Session, state: str, county: str) -> tuple[FeeRule | None, FeeRule | None]:
    rows = session.scalars(select(FeeRule).where(FeeRule.state == state.upper())).all()
    state_rule = next((r for r in rows if r.county == ""), None)
    county_rule = next((r for r in rows if r.county and _county_key(r.county) == _county_key(county)), None)
    return county_rule, state_rule


def band_pct(session: Session, amount_cents: int) -> float:
    bands = session.scalars(select(FeeBand)).all()
    bounded = sorted((b for b in bands if b.up_to_cents is not None), key=lambda b: b.up_to_cents)
    for b in bounded:
        if amount_cents <= b.up_to_cents:
            return b.pct
    top = next((b for b in bands if b.up_to_cents is None), None)
    return top.pct if top else config.DEFAULT_FEE_PCT


def quote(session: Session, record: SurplusRecord) -> tuple[float, dict]:
    """(fee %, how it was worked out) for a record."""
    county_rule, state_rule = _rules(session, record.state, record.county)
    base, base_from = config.DEFAULT_FEE_PCT, "default"
    for rule, label in ((county_rule, "county"), (state_rule, "state")):
        if rule is not None and rule.base_pct is not None:
            base, base_from = rule.base_pct, label
            break
    band = band_pct(session, record.amount_cents)
    pct = (base + band) / 2
    cap, cap_from, cap_source = None, "", ""
    for rule, label in ((county_rule, "county"), (state_rule, "state")):
        if rule is not None and rule.legal_max_pct is not None:
            cap, cap_from, cap_source = rule.legal_max_pct, label, rule.legal_source
            break
    if cap is not None:
        pct = min(pct, cap)
    pct = round(pct * 2) / 2
    return pct, {"county_pct": base, "county_pct_from": base_from, "amount_band_pct": band,
                 "legal_max_pct": cap, "legal_max_from": cap_from, "legal_source": cap_source,
                 "average_pct": round((base + band) / 2, 2), "final_pct": pct}


def for_claim(session: Session, claim: Claim) -> float:
    """The claim's fee, fixing it from the current rules the first time it's needed."""
    if claim.fee_pct is None:
        claim.fee_pct, claim.fee_basis = quote(session, claim.record)
    return claim.fee_pct


def fee_cents(amount_cents: int, pct: float) -> int:
    return round(amount_cents * pct / 100)
