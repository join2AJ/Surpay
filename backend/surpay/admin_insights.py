"""Staff dashboard: where people are in the process, attorney performance, and click-through detail
for any record, person or signed document (with where each value came from)."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select

from . import attorney_pay, audit, documents, esign
from .admin_api import _aware, _log, _user_row, admin_claim
from .demo import is_demo_attorney, is_demo_claim, is_demo_user
from .deps import Admin, Client, DbSession
from .filing_methods import method_for
from .legal import record_deadline
from .models import AuditLog, Claim, CountySource, ScrapeRun, SignedDocument, SurplusRecord, User

router = APIRouter(tags=["admin"])

STAGES = ["requested", "identity_submitted", "agreement_signed", "identity_verified", "attorney_assigned",
          "filed", "hearing_pending", "approved", "paid"]
STAGE_LABELS = {"requested": "Claim started", "identity_submitted": "ID submitted", "agreement_signed": "Agreement signed",
                "identity_verified": "ID verified, waiting for attorney", "attorney_assigned": "Attorney working on it",
                "filed": "Filed", "hearing_pending": "Waiting for county / court", "approved": "Approved",
                "paid": "Money released", "denied": "Denied", "withdrawn": "Withdrawn"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days(a: datetime | None, b: datetime | None = None) -> float | None:
    a = _aware(a)
    if a is None:
        return None
    return round(((_aware(b) or _now()) - a).total_seconds() / 86400, 1)


def _claims(session, scope) -> list[Claim]:
    rows = session.scalars(select(Claim)).all()
    return [c for c in rows if is_demo_claim(c)] if scope.demo else rows


def _users(session, scope) -> list[User]:
    rows = session.scalars(select(User)).all()
    if scope.demo:
        rows = [u for u in rows if is_demo_user(u) or (u.attorney is not None and is_demo_attorney(u.attorney))]
    return rows


@router.get("/admin/insights")
def insights(scope: Admin, session: DbSession) -> dict:
    """Where claimants and attorneys are, where they get stuck, and how attorneys are doing."""
    claims_ = _claims(session, scope)
    users = _users(session, scope)
    claimants = [u for u in users if u.role == "claimant"]

    # Claimant journey: how many reached each step (a later step implies the earlier ones).
    reached = Counter()
    for c in claims_:
        if c.status in STAGES:
            for s in STAGES[: STAGES.index(c.status) + 1]:
                reached[s] += 1
        elif c.status == "denied":
            for s in STAGES[: STAGES.index("filed") + 1]:
                reached[s] += 1
    journey = [{"step": "Accounts", "key": "accounts", "count": len(claimants)},
               {"step": "ID submitted", "key": "id_submitted", "count": sum(1 for u in claimants if u.identity)},
               {"step": "ID approved", "key": "id_approved",
                "count": sum(1 for u in claimants if u.identity and u.identity.review_status == "approved")}]
    journey += [{"step": STAGE_LABELS[s], "key": s, "count": reached[s]} for s in STAGES]
    for i, step in enumerate(journey):
        prev = journey[i - 1]["count"] if i else step["count"]
        step["pct_of_previous"] = round(100 * step["count"] / prev) if prev else None

    # Where claims are now, and how long they've been there.
    by_stage = []
    for s in STAGES + ["denied", "withdrawn"]:
        here = [c for c in claims_ if c.status == s]
        if not here:
            continue
        ages = [_days(max([e.created_at for e in c.events], default=c.created_at)) or 0 for c in here]
        oldest = max(here, key=lambda c: _days(max([e.created_at for e in c.events], default=c.created_at)) or 0)
        by_stage.append({"stage": s, "label": STAGE_LABELS.get(s, s), "claims": len(here),
                         "amount_cents": sum(c.record.amount_cents for c in here),
                         "median_days_here": round(median(ages), 1), "longest_days_here": round(max(ages), 1),
                         "oldest_claim": oldest.id})

    # Claimants who haven't finished onboarding.
    onboarding = Counter()
    for u in claimants:
        if u.identity is None:
            onboarding["Signed up, no ID yet"] += 1
        elif u.identity.review_status == "pending":
            onboarding["ID waiting for review"] += 1
        elif u.identity.review_status == "rejected":
            onboarding["ID rejected, needs resubmitting"] += 1
        elif not u.claims:
            onboarding["Verified, no claim started"] += 1

    # Attorneys.
    lawyers = []
    for u in users:
        a = u.attorney
        if a is None:
            continue
        mine = [c for c in claims_ if c.attorney_id == u.id]
        accepted = [c for c in mine if c.accepted_at]
        response = [h for h in (_days(c.assigned_at, c.accepted_at) for c in accepted) if h is not None]
        lawyers.append({
            "user_id": u.id, "app_number": u.app_number, "name": a.full_name, "firm": a.firm, "status": a.status,
            "available": a.available, "counties": a.counties,
            "offered_now": sum(1 for c in mine if c.assignment_status == "offered"),
            "active": sum(1 for c in mine if c.assignment_status == "accepted" and c.status not in ("paid", "denied", "withdrawn")),
            "filed": sum(1 for c in mine if c.status in ("filed", "hearing_pending", "approved", "paid", "denied")),
            "paid": sum(1 for c in mine if c.status == "paid"),
            "declined": sum(1 for c in claims_ if u.id in (c.declined_by or [])),
            "median_response_days": round(median(response), 1) if response else None,
            "by_stage": dict(Counter(c.status for c in mine if c.assignment_status == "accepted")),
            "earned_cents": sum(c.attorney_fee_cents for c in mine if c.payout_status == "paid"),
            "due_cents": sum(c.attorney_fee_cents for c in mine if c.payout_status == "due"),
            "pipeline_cents": sum(c.attorney_fee_cents for c in mine if c.assignment_status == "accepted"
                                  and c.payout_status == ""),
        })

    # Documents: how far clients are with their checklists.
    docs = Counter()
    for c in claims_:
        for r in c.document_requests:
            docs[(documents.KINDS.get(r.kind, documents.KINDS["other"])[0], r.status)] += 1
    doc_rows = {}
    for (label, st), n in docs.items():
        doc_rows.setdefault(label, {"document": label, "requested": 0, "uploaded": 0, "accepted": 0, "rejected": 0})[st] = n

    # Money: what Surpay keeps after paying attorneys.
    margins = []
    for c in claims_:
        if c.attorney_id and c.status not in ("withdrawn", "denied"):
            q = attorney_pay.quote(session, c)
            margins.append({"claim_id": c.id, "client_fee_cents": q["client_fee_cents"],
                            "attorney_cents": c.attorney_fee_cents or q["total_cents"],
                            "margin_cents": q["client_fee_cents"] - (c.attorney_fee_cents or q["total_cents"]),
                            "low_margin": q["low_margin"]})

    # Sign-ups by week, last 8 weeks.
    weeks = []
    start = _now() - timedelta(weeks=8)
    for w in range(8):
        a, b = start + timedelta(weeks=w), start + timedelta(weeks=w + 1)
        weeks.append({"week_of": a.date().isoformat(),
                      "claimants": sum(1 for u in claimants if a <= _aware(u.created_at) < b),
                      "claims": sum(1 for c in claims_ if a <= _aware(c.created_at) < b)})

    by_state = Counter((c.record.state) for c in claims_)
    return {
        "journey": journey, "by_stage": by_stage, "onboarding": dict(onboarding), "attorneys": lawyers,
        "documents": sorted(doc_rows.values(), key=lambda r: r["document"]),
        "margin": {"cases": len(margins), "client_fees_cents": sum(m["client_fee_cents"] for m in margins),
                   "attorney_cents": sum(m["attorney_cents"] for m in margins),
                   "surpay_cents": sum(m["margin_cents"] for m in margins),
                   "low_margin_claims": [m["claim_id"] for m in margins if m["low_margin"]]},
        "weeks": weeks, "claims_by_state": dict(by_state),
        "pay_schedule": attorney_pay.schedule_text(session),
    }


# --- Record detail, with where it came from ------------------------------------------------------------

def _file_type(url: str, registry_format: str = "") -> str:
    u = url.lower().split("?")[0]
    for ext, label in ((".pdf", "PDF"), (".xlsx", "Excel"), (".xls", "Excel"), (".csv", "CSV"), (".docx", "Word"),
                       (".doc", "Word"), (".png", "Image"), (".jpg", "Image"), (".jpeg", "Image")):
        if u.endswith(ext):
            return label
    if "documentcenter/view" in u or "/edoc/" in u:
        return "PDF"
    fmt = registry_format.lower()
    return {"pdf": "PDF", "xlsx": "Excel", "csv": "CSV", "html": "Web page", "docx/pdf": "Word or PDF"}.get(fmt, "Web page" if u else "Unknown")


def provenance(session, r: SurplusRecord) -> dict:
    from .scrapers import SOURCES
    cls = SOURCES.get(r.source)
    reg = session.scalars(select(CountySource).where(CountySource.scraper.like(f"%{r.source}%"))).first()
    last_ok = session.scalars(select(ScrapeRun).where(ScrapeRun.source == r.source, ScrapeRun.ok.is_(True))
                              .order_by(ScrapeRun.id.desc()).limit(1)).first()
    return {"source": r.source, "description": cls.description if cls else ("Demo data" if r.source == "demo" else ""),
            "publisher": reg.publisher if reg else "", "list_page": reg.list_url if reg else "",
            "file_url": r.source_url, "file_type": _file_type(r.source_url, reg.format if reg else ""),
            "update_frequency": reg.update_frequency if reg else "", "registry_notes": reg.notes if reg else "",
            "first_seen": _aware(r.first_seen), "last_seen": _aware(r.last_seen),
            "last_successful_run": _aware(last_ok.finished_at or last_ok.started_at) if last_ok else None,
            "source_key": r.source_key}


@router.get("/admin/records/{record_id}")
def record_detail(record_id: int, scope: Admin, session: DbSession) -> dict:
    r = session.get(SurplusRecord, record_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    clock = record_deadline(r)
    claims_ = session.scalars(select(Claim).where(Claim.record_id == r.id)).all()
    return {
        "id": r.id, "state": r.state, "county": r.county, "reference": r.reference, "owner_name": r.owner_name,
        "owner_address": r.owner_address, "amount_cents": r.amount_cents, "sale_type": r.sale_type,
        "sale_date": r.sale_date, "status": r.status, "deadline": clock,
        "provenance": provenance(session, r),
        # Each field and the column of the county's list it was read from (as the scraper kept it).
        "raw": r.raw or {},
        "filing_method": method_for(r.state, r.county),
        "claims": [{"id": c.id, "ref": f"SP-{c.id:06d}", "status": c.status,
                    "claimant": c.user.full_name if not scope.demo or is_demo_user(c.user) else "(tester)"}
                   for c in claims_],
    }


# --- Person detail ------------------------------------------------------------------------------------

@router.get("/admin/users/{user_id}")
def user_detail(user_id: int, scope: Admin, session: DbSession, client: Client) -> dict:
    u = session.get(User, user_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    scope.check(is_demo_user(u) or (u.attorney is not None and is_demo_attorney(u.attorney)))
    _log(session, "admin.user_viewed", client, entity_type="user", entity_id=u.id)
    session.commit()
    mine = session.scalars(select(Claim).where(or_(Claim.user_id == u.id, Claim.attorney_id == u.id))).all()
    signed = session.scalars(select(SignedDocument).where(SignedDocument.user_id == u.id)
                             .order_by(SignedDocument.id.desc())).all()
    return {
        **_user_row(u), "app_number": u.app_number, "phone": u.phone,
        "email_verified_at": u.email_verified_at, "phone_verified_at": u.phone_verified_at,
        "addresses": [f"{a.street}, {a.city}, {a.state} {a.zip}" for a in u.own_addresses],
        "claims": [{"id": c.id, "ref": f"SP-{c.id:06d}", "status": c.status, "as": "claimant" if c.user_id == u.id else "attorney",
                    "county": f"{c.record.county}, {c.record.state}", "amount_cents": c.record.amount_cents} for c in mine],
        "documents": [esign.out(d) for d in signed],
        "activity": _activity(session, u.id, [c.id for c in mine]),
    }


def _activity(session, user_id: int, claim_ids: list[int], limit: int = 300) -> list[dict]:
    stmt = select(AuditLog).where(or_(
        AuditLog.actor_id == user_id,
        (AuditLog.entity_type == "user") & (AuditLog.entity_id == user_id),
        (AuditLog.entity_type == "claim") & AuditLog.entity_id.in_(claim_ids or [-1]),
    )).order_by(AuditLog.id.desc()).limit(limit)
    return [audit.entry_out(e) for e in session.scalars(stmt)]


@router.get("/admin/claims/{claim_id}/detail")
def claim_detail(claim_id: int, scope: Admin, session: DbSession, client: Client) -> dict:
    c = session.get(Claim, claim_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    scope.check(is_demo_claim(c))
    _log(session, "admin.claim_viewed", client, entity_type="claim", entity_id=c.id)
    session.commit()
    signed = session.scalars(select(SignedDocument).where(SignedDocument.claim_id == c.id)).all()
    return {**admin_claim(c, scope), "pay": attorney_pay.quote(session, c), "provenance": provenance(session, c.record),
            "signed_documents": [esign.out(d) for d in signed], "activity": _activity(session, -1, [c.id]),
            "events": [{"status": e.status, "note": e.note, "at": _aware(e.created_at)} for e in c.events]}


@router.get("/admin/pay")
def pay_bands(scope: Admin, session: DbSession) -> dict:
    return {"bands": [{"id": b.id, "up_to_cents": b.up_to_cents, "base_cents": b.base_cents, "pct": b.pct,
                       "cap_cents": b.cap_cents} for b in attorney_pay.bands(session)],
            "heir_bonus_cents": attorney_pay.HEIR_BONUS_CENTS, "hearing_bonus_cents": attorney_pay.HEARING_BONUS_CENTS,
            "schedule": attorney_pay.schedule_text(session)}


@router.post("/admin/pay/{band_id}")
def update_pay_band(band_id: int, body: dict, scope: Admin, session: DbSession, client: Client) -> dict:
    from .models import AttorneyFeeBand
    scope.read_only()
    b = session.get(AttorneyFeeBand, band_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    try:
        base = int(body.get("base_cents", b.base_cents))
        pct = float(body.get("pct", b.pct))
        cap = body.get("cap_cents", b.cap_cents)
        cap = None if cap in (None, "") else int(cap)
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Numbers only") from None
    if base < 0 or not 0 <= pct <= 20 or (cap is not None and cap < base):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Check the amounts")
    before = {"base_cents": b.base_cents, "pct": b.pct, "cap_cents": b.cap_cents}
    b.base_cents, b.pct, b.cap_cents = base, pct, cap
    _log(session, "admin.pay_band_changed", client, band_id=b.id, before=before,
         after={"base_cents": base, "pct": pct, "cap_cents": cap})
    session.commit()
    return pay_bands(scope, session)
