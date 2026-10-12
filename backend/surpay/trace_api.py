"""Finding owners and inviting them: staff endpoints, and the public invitation and opt-out pages."""

from html import escape

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import audit, config, outreach, trace
from .admin_api import _log
from .deps import Admin, Client, DbSession
from .models import CountySource, OwnerContact, Outreach, SurplusRecord, TraceRun

router = APIRouter(tags=["trace"])


class TraceBatchIn(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    min_cents: int = 0


class ContactIn(BaseModel):
    kind: str = Field(pattern=r"^(address|email|phone|profile|obituary|link)$")
    value: str = Field(min_length=3, max_length=500)
    label: str = ""
    source_url: str = ""
    note: str = ""
    confidence: str = Field(default="medium", pattern=r"^(low|medium|high)$")
    # The source's address history includes the property that was sold: strong proof it's the same person.
    matches_property: bool = False


class ContactUpdate(BaseModel):
    do_not_contact: bool


class OutreachIn(BaseModel):
    channel: str = Field(pattern=r"^(letter|email|in_app)$")
    contact_id: int | None = None


def _record(session, scope, record_id: int, public: bool = False) -> SurplusRecord:
    """County records are public, so the admin demo may search any of them (public=True); acting on a
    real person (adding contacts, sending letters or emails) stays with real staff."""
    r = session.get(SurplusRecord, record_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    if not public:
        scope.check(r.source == "demo")
    return r


# The admin demo is open to anyone testing the app: it may run this many searches an hour, in total.
DEMO_TRACES_PER_HOUR = 30


def _demo_quota(session) -> None:
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func
    used = session.scalar(select(func.count()).select_from(TraceRun).where(
        TraceRun.by == "demo_admin", TraceRun.started_at > datetime.now(timezone.utc) - timedelta(hours=1))) or 0
    if used >= DEMO_TRACES_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "The admin demo has used its searches for this hour. Try again later.")


def _mask(kind: str, value: str) -> str:
    if kind == "email":
        local, _, domain = value.partition("@")
        return f"{local[:1]}•••@{domain}"
    if kind == "phone":
        return "•••-•••-" + "".join(ch for ch in value if ch.isdigit())[-4:]
    if kind == "user":
        return "a verified Surpay user"
    return value


def contact_out(c: OwnerContact, mask: bool = False) -> dict:
    return {"id": c.id, "kind": c.kind, "value": _mask(c.kind, c.value) if mask else c.value, "label": c.label, "source": c.source,
            "source_url": c.source_url, "confidence": c.confidence, "note": c.note,
            "do_not_contact": c.do_not_contact, "created_at": c.created_at}


def run_out(t: TraceRun, mask: bool = False) -> dict:
    steps = t.steps
    if mask:  # don't reveal which real user matched
        steps = [{**s, "note": "Matches a verified Surpay user" if s.get("source") == "Surpay users" and s.get("found")
                  else s.get("note", "")} for s in steps]
    return {"id": t.id, "record_id": t.record_id, "status": t.status, "steps": steps, "deceased": t.deceased,
            "started_at": t.started_at, "finished_at": t.finished_at, "by": t.by}


def outreach_out(o: Outreach) -> dict:
    return {"id": o.id, "record_id": o.record_id, "contact_id": o.contact_id, "channel": o.channel, "code": o.code,
            "status": o.status, "created_at": o.created_at, "sent_at": o.sent_at, "user_id": o.user_id,
            "link": outreach.link(o.code)}


@router.get("/admin/trace")
def trace_overview(scope: Admin, session: DbSession, status_: str = "", limit: int = 200) -> dict:
    """The latest trace of each record, with what was found, plus totals."""
    stmt = select(TraceRun).order_by(TraceRun.id.desc()).limit(min(limit, 1000) * 2)
    latest: dict[int, TraceRun] = {}
    for t in session.scalars(stmt):
        latest.setdefault(t.record_id, t)
    rows = []
    for t in latest.values():
        r = session.get(SurplusRecord, t.record_id)
        if r is None or (status_ and t.status != status_):
            continue
        contacts = session.scalars(select(OwnerContact).where(OwnerContact.record_id == r.id)).all()
        rows.append({**run_out(t, mask=scope.demo and r.source != "demo"), "owner_name": r.owner_name, "county": r.county, "state": r.state,
                     "amount_cents": r.amount_cents, "contacts": len(contacts),
                     "usable": sum(1 for c in contacts if c.kind in ("email", "address", "user") and not c.do_not_contact),
                     "outreach": len(session.scalars(select(Outreach).where(Outreach.record_id == r.id)).all())})
    return {"summary": trace.summary(session), "runs": rows[:limit],
            "queue": len(trace.queue(session, limit=50)), "demo": scope.demo,
            "demo_searches_per_hour": DEMO_TRACES_PER_HOUR if scope.demo else None}


@router.post("/admin/trace/run")
def trace_run(body: TraceBatchIn, scope: Admin, session: DbSession, client: Client) -> dict:
    """Trace the next records in the queue (biggest first), each checking at most four places."""
    if scope.demo:
        # The demo searches the real queue too (county records are public), a few at a time.
        _demo_quota(session)
        records = trace.queue(session, limit=min(body.limit, 5))
        users = trace._verified_users(session)
        runs = [trace.trace(session, r, by="demo_admin", users=users) for r in records]
        session.commit()
    else:
        runs = trace.trace_batch(session, body.limit, body.min_cents)
    _log(session, "admin.trace_batch", client, records=[t.record_id for t in runs])
    session.commit()
    return {"runs": [run_out(t, mask=scope.demo) for t in runs]}


@router.get("/admin/records/{record_id}/trace")
def record_trace(record_id: int, scope: Admin, session: DbSession, client: Client) -> dict:
    r = _record(session, scope, record_id, public=True)
    mask = scope.demo and r.source != "demo"
    _log(session, "admin.trace_viewed", client, entity_type="record", entity_id=r.id)
    session.commit()
    reg = session.scalars(select(CountySource).where(CountySource.scraper.like(f"%{r.source}%"))).first()
    name, deceased = trace.person_name(r.owner_name)
    city, state = trace.place(r)
    return {
        "record_id": r.id, "owner_name": r.owner_name, "person": name, "deceased_hint": deceased,
        "search_place": f"{city}, {state}", "search_provider": trace.search_ready() or None,
        "runs": [run_out(t, mask) for t in session.scalars(select(TraceRun).where(TraceRun.record_id == r.id)
                                                           .order_by(TraceRun.id.desc()))],
        "contacts": [contact_out(c, mask) for c in session.scalars(select(OwnerContact).where(OwnerContact.record_id == r.id))],
        "outreach": [] if mask else [outreach_out(o) for o in session.scalars(select(Outreach).where(Outreach.record_id == r.id))],
        # The admin demo can search real county records but not contact real people.
        "read_only": mask,
        "manual_sources": trace.manual_sources(r, reg.list_url if reg else ""),
    }


@router.post("/admin/records/{record_id}/trace")
def trace_one(record_id: int, scope: Admin, session: DbSession, client: Client) -> dict:
    r = _record(session, scope, record_id, public=True)
    if scope.demo and r.source != "demo":
        _demo_quota(session)
    t = trace.trace(session, r, by="demo_admin" if scope.demo else "admin")
    _log(session, "admin.trace_run", client, entity_type="record", entity_id=r.id, status=t.status)
    session.commit()
    return record_trace(record_id, scope, session, client)


@router.post("/admin/records/{record_id}/contacts")
def add_contact(record_id: int, body: ContactIn, scope: Admin, session: DbSession, client: Client) -> dict:
    r = _record(session, scope, record_id)
    note = body.note.strip()
    if body.matches_property:
        note = (note + " · " if note else "") + f"Address history includes the sold property ({r.owner_address or r.reference})"
    c = OwnerContact(record_id=r.id, kind=body.kind, value=body.value.strip(), label=body.label, source="manual",
                     source_url=body.source_url, confidence="high" if body.matches_property else body.confidence, note=note)
    session.add(c)
    session.flush()
    _log(session, "admin.contact_added", client, entity_type="record", entity_id=r.id, kind=body.kind)
    session.commit()
    return record_trace(record_id, scope, session, client)


@router.post("/admin/contacts/{contact_id}")
def update_contact(contact_id: int, body: ContactUpdate, scope: Admin, session: DbSession, client: Client) -> dict:
    c = session.get(OwnerContact, contact_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    _record(session, scope, c.record_id)
    c.do_not_contact = body.do_not_contact
    _log(session, "admin.contact_updated", client, entity_type="record", entity_id=c.record_id,
         contact_id=c.id, do_not_contact=body.do_not_contact)
    session.commit()
    return contact_out(c)


@router.post("/admin/records/{record_id}/outreach")
def add_outreach(record_id: int, body: OutreachIn, scope: Admin, session: DbSession, client: Client) -> dict:
    r = _record(session, scope, record_id)
    contact = session.get(OwnerContact, body.contact_id) if body.contact_id else None
    if contact is not None and contact.record_id != r.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if body.channel == "email" and scope.demo:
        scope.read_only()
    o = outreach.create(session, r, body.channel, contact)
    _log(session, "admin.outreach_created", client, entity_type="record", entity_id=r.id, channel=o.channel,
         code=o.code, status=o.status)
    session.commit()
    return outreach_out(o)


@router.get("/admin/outreach")
def list_outreach(scope: Admin, session: DbSession, channel: str = "", status_: str = "") -> list[dict]:
    stmt = select(Outreach).order_by(Outreach.id.desc())
    if channel:
        stmt = stmt.where(Outreach.channel == channel)
    if status_:
        stmt = stmt.where(Outreach.status == status_)
    out = []
    for o in session.scalars(stmt.limit(500)):
        r = session.get(SurplusRecord, o.record_id)
        if r is None or (scope.demo and r.source != "demo"):
            continue
        out.append({**outreach_out(o), "owner_name": r.owner_name, "county": r.county, "state": r.state})
    return out


@router.get("/admin/outreach/letters.pdf")
def letters(scope: Admin, session: DbSession, client: Client, ids: str = "") -> Response:
    """Ready-to-print letters: the ones listed in ids, else every letter not sent yet."""
    stmt = select(Outreach).where(Outreach.channel == "letter")
    stmt = stmt.where(Outreach.id.in_([int(x) for x in ids.split(",") if x.strip().isdigit()])) if ids \
        else stmt.where(Outreach.status == "ready")
    items = [o for o in session.scalars(stmt.order_by(Outreach.id))
             if not scope.demo or session.get(SurplusRecord, o.record_id).source == "demo"]
    if not items:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No letters to print")
    _log(session, "admin.letters_printed", client, outreach=[o.id for o in items])
    session.commit()
    return Response(outreach.letters_pdf(session, items), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="surpay-letters.pdf"', "Cache-Control": "no-store"})


@router.post("/admin/outreach/mark-sent")
def mark_sent(body: dict, scope: Admin, session: DbSession, client: Client) -> dict:
    from datetime import datetime, timezone
    n = 0
    for oid in body.get("ids", []):
        o = session.get(Outreach, int(oid))
        if o is not None and o.status == "ready" and (not scope.demo or session.get(SurplusRecord, o.record_id).source == "demo"):
            o.status, o.sent_at = "sent", datetime.now(timezone.utc)
            n += 1
    _log(session, "admin.outreach_marked_sent", client, count=n)
    session.commit()
    return {"marked": n}


# --- Public pages: the invitation link and opting out ------------------------------------------------

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{title}</title><style>body{{font:16px/1.55 system-ui,sans-serif;max-width:560px;margin:40px auto;
padding:0 16px;color:#0f172a;background:#f5f7fb}}.card{{background:#fff;border:1px solid #e3e8f0;border-radius:14px;padding:20px}}
h1{{font-size:22px}}code{{font-size:20px;letter-spacing:2px;background:#e6f4ee;padding:4px 10px;border-radius:8px}}
button,a.btn{{display:inline-block;background:#0b6e4f;color:#fff;border:0;border-radius:10px;padding:10px 16px;font:inherit;
font-weight:600;text-decoration:none;cursor:pointer}}.muted{{color:#5b6474;font-size:14px}}</style></head><body><div class="card">{body}</div></body></html>"""


@router.get("/i/{code}", response_class=HTMLResponse, include_in_schema=False)
def invitation(code: str, session: DbSession, client: Client) -> HTMLResponse:
    o = session.scalar(select(Outreach).where(Outreach.code == code.upper()))
    if o is None or o.status == "opted_out":
        return HTMLResponse(_PAGE.format(title="Surpay", body="<h1>This link isn't active</h1>"), status_code=404)
    r = session.get(SurplusRecord, o.record_id)
    if o.status in ("ready", "sent"):
        o.status = "opened"
        audit.record(session, "outreach.opened", actor_type="system", entity_type="record", entity_id=r.id, client=client,
                     details={"code": o.code})
        session.commit()
    app = (f'<p><a class="btn" href="{escape(config.APP_URL)}">Get the {escape(config.COMPANY_NAME)} app</a></p>'
           if config.APP_URL else f"<p>Get the {escape(config.COMPANY_NAME)} app on your Android phone.</p>")
    body = (f"<h1>Money from a property sale may be yours</h1>"
            f"<p>Public records show that {escape(outreach._holder(r))} may be holding money left over from the sale of a "
            f"property (county reference {escape(r.reference)}). It belongs to the former owner or their heirs.</p>"
            f"{app}<p>When you sign up, enter your invitation code:</p><p><code>{escape(o.code)}</code></p>"
            f"<p class='muted'>We verify your identity before showing any details, so nobody else can claim it. "
            f"You can also confirm the record with the county office directly.</p>"
            f"<p class='muted'><a href='{escape(config.PUBLIC_URL)}/optout/{escape(o.code)}'>Don't contact me again</a></p>")
    return HTMLResponse(_PAGE.format(title="Funds may be yours", body=body))


@router.get("/optout/{code}", response_class=HTMLResponse, include_in_schema=False)
def optout_page(code: str) -> HTMLResponse:
    body = (f"<h1>Stop hearing from us</h1><p>We'll stop contacting you about this record.</p>"
            f"<form method='post'><button type='submit'>Don't contact me again</button></form>")
    return HTMLResponse(_PAGE.format(title="Opt out", body=body))


@router.post("/optout/{code}", response_class=HTMLResponse, include_in_schema=False)
def optout(code: str, session: DbSession, client: Client) -> HTMLResponse:
    r = outreach.opt_out(session, code)
    if r is not None:
        audit.record(session, "outreach.opted_out", actor_type="system", entity_type="record", entity_id=r.id,
                     client=client, details={"code": code.upper()})
        session.commit()
    return HTMLResponse(_PAGE.format(title="Done", body="<h1>Done</h1><p>We won't contact you about this again.</p>"))


class ContactImportIn(BaseModel):
    # CSV lines: record_id,kind,value,source_url,note,matches_property (header line optional)
    text: str = Field(min_length=3, max_length=200_000)


@router.post("/admin/contacts-import")
def import_contacts(body: ContactImportIn, scope: Admin, session: DbSession, client: Client) -> dict:
    """Add many contacts at once from pasted CSV lines. Each is encrypted, checked and audited like a
    single add; bad lines are reported and skipped."""
    import csv
    import io
    results = []
    kinds = {"address", "email", "phone", "profile", "obituary", "link"}
    for n, row in enumerate(csv.reader(io.StringIO(body.text.strip())), 1):
        row = [c.strip() for c in row]
        if not row or not any(row) or row[0].lower() in ("record_id", "record"):
            continue
        try:
            record_id, kind, value = int(row[0]), row[1].lower(), row[2]
        except (ValueError, IndexError):
            results.append({"line": n, "ok": False, "error": "Needs at least: record_id,kind,value"})
            continue
        url = row[3] if len(row) > 3 else ""
        note = row[4] if len(row) > 4 else ""
        matches = len(row) > 5 and row[5].lower() in ("yes", "y", "true", "1", "x")
        r = session.get(SurplusRecord, record_id)
        if r is None or (scope.demo and r.source != "demo"):
            results.append({"line": n, "ok": False, "error": f"Record {record_id} not found" if r is None
                            else "Real people's contacts can only be added with the staff token"})
            continue
        if kind not in kinds or len(value) < 3:
            results.append({"line": n, "ok": False, "error": f"Type must be one of {', '.join(sorted(kinds))}"})
            continue
        if url and not url.startswith(("http://", "https://")):
            results.append({"line": n, "ok": False, "error": "Source URL must start with https://"})
            continue
        if matches:
            note = (note + " · " if note else "") + f"Address history includes the sold property ({r.owner_address or r.reference})"
        dup = [c for c in session.scalars(select(OwnerContact).where(OwnerContact.record_id == r.id))
               if c.kind == kind and c.value.lower() == value.lower()]
        if dup:
            results.append({"line": n, "ok": False, "error": "Already saved", "contact_id": dup[0].id})
            continue
        c = OwnerContact(record_id=r.id, kind=kind, value=value, source="manual", source_url=url[:2000],
                         confidence="high" if matches else "medium", note=note[:2000])
        session.add(c)
        session.flush()
        results.append({"line": n, "ok": True, "record_id": r.id, "contact_id": c.id, "kind": kind})
    added = [x for x in results if x["ok"]]
    _log(session, "admin.contacts_imported", client, added=len(added),
         records=sorted({x["record_id"] for x in added}))
    session.commit()
    return {"added": len(added), "results": results}
