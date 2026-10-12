"""What a partner attorney is paid for a case.

A single flat fee pays the same for a $3,000 claim and a $300,000 one, though larger claims are
more often contested by lienholders, need more proof and carry more risk for the attorney. So pay
scales with the claim, but less than proportionally:

    pay = base for the claim's size band + pct of the amount, capped per band
          + a bonus for heir / probate claims (more documents, sometimes a probate filing)
          + a bonus once a contested hearing is needed

It is paid when the money is released (and a smaller closing fee if the court denies the claim, so
attorneys aren't punished for honest losses). Surpay keeps the client's fee minus this pay; the
admin overview shows that margin for every case.

Have ethics counsel in each state review the arrangement (ABA Model Rules 1.8(f), 5.4 and 7.2)
before real cases.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AttorneyFeeBand, Claim

# (up to, base, pct of amount, cap) in cents; None = and above.
DEFAULT_BANDS = [
    (1_000_000, 60_000, 0.0, None),            # up to $10k: $600
    (5_000_000, 75_000, 1.5, 150_000),         # up to $50k: $750 + 1.5%, max $1,500
    (10_000_000, 125_000, 1.5, 275_000),       # up to $100k: $1,250 + 1.5%, max $2,750
    (None, 200_000, 1.25, 600_000),            # above: $2,000 + 1.25%, max $6,000
]
HEIR_BONUS_CENTS = 50_000          # death certificate, heirship proof, sometimes a probate filing
HEARING_BONUS_CENTS = 50_000       # a contested hearing in court
DENIED_FEE_SHARE = 0.5             # paid if the court or county denies the claim
LOW_MARGIN_SHARE = 0.4             # flag cases where Surpay keeps less than 40% of the client's fee


def seed_bands(session: Session) -> None:
    if session.scalar(select(AttorneyFeeBand.id).limit(1)) is None:
        for up_to, base, pct, cap in DEFAULT_BANDS:
            session.add(AttorneyFeeBand(up_to_cents=up_to, base_cents=base, pct=pct, cap_cents=cap))
        session.commit()


def bands(session: Session) -> list[AttorneyFeeBand]:
    rows = session.scalars(select(AttorneyFeeBand)).all()
    return sorted(rows, key=lambda b: (b.up_to_cents is None, b.up_to_cents or 0))


def band_for(session: Session, amount_cents: int) -> AttorneyFeeBand | None:
    for b in bands(session):
        if b.up_to_cents is None or amount_cents <= b.up_to_cents:
            return b
    return None


def quote(session: Session, claim: Claim) -> dict:
    """The attorney's pay for this case and how it was worked out."""
    amount = claim.record.amount_cents
    b = band_for(session, amount)
    if b is None:
        base, extra, cap = 50_000, 0, None
    else:
        base = b.base_cents
        extra = round(amount * (b.pct or 0) / 100)
        cap = b.cap_cents
    size_pay = base + extra if cap is None else min(base + extra, cap)
    heir = HEIR_BONUS_CENTS if claim.relative_id else 0
    hearing = HEARING_BONUS_CENTS if claim.status in ("hearing_pending", "approved", "paid") and _had_hearing(claim) else 0
    total = size_pay + heir + hearing
    client_fee = round(amount * (claim.fee_pct or 0) / 100)
    return {
        "total_cents": total, "size_cents": size_pay, "heir_bonus_cents": heir, "hearing_bonus_cents": hearing,
        "band": None if b is None else {"up_to_cents": b.up_to_cents, "base_cents": b.base_cents, "pct": b.pct,
                                        "cap_cents": b.cap_cents},
        "if_denied_cents": round(size_pay * DENIED_FEE_SHARE),
        "client_fee_cents": client_fee, "surpay_margin_cents": client_fee - total,
        "low_margin": client_fee > 0 and (client_fee - total) < client_fee * LOW_MARGIN_SHARE,
        "explanation": _explain(b, size_pay, heir, hearing),
    }


def _had_hearing(claim: Claim) -> bool:
    return any(e.status == "hearing_pending" for e in claim.events)


def _explain(b: AttorneyFeeBand | None, size_pay: int, heir: int, hearing: int) -> str:
    parts = [f"${size_pay / 100:,.0f} for a claim of this size"]
    if heir:
        parts.append(f"${heir / 100:,.0f} for an heir claim")
    if hearing:
        parts.append(f"${hearing / 100:,.0f} for the hearing")
    return " + ".join(parts) + ", paid when the money is released."


def apply(session: Session, claim: Claim) -> None:
    """Fix the attorney's pay on the claim (on offer, and again if a hearing is added)."""
    claim.attorney_fee_cents = quote(session, claim)["total_cents"]


def schedule_text(session: Session) -> str:
    """The pay schedule in words, for the partner terms."""
    lines = []
    low = 0
    for b in bands(session):
        size = f"over ${low / 100:,.0f}" if b.up_to_cents is None else f"${low / 100:,.0f} to ${b.up_to_cents / 100:,.0f}"
        pay = f"${b.base_cents / 100:,.0f}"
        if b.pct:
            pay += f" + {b.pct:g}% of the amount recovered"
        if b.cap_cents:
            pay += f", up to ${b.cap_cents / 100:,.0f}"
        lines.append(f"- Claims of {size}: {pay}")
        low = (b.up_to_cents or 0) + 1
    lines.append(f"- Plus ${HEIR_BONUS_CENTS / 100:,.0f} for a claim made by an heir, and "
                 f"${HEARING_BONUS_CENTS / 100:,.0f} if a contested hearing is needed")
    lines.append(f"- If the claim is denied after you file, {int(DENIED_FEE_SHARE * 100)}% of the size-based amount")
    return "\n".join(lines)
