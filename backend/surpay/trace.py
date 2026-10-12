"""Finding the owners of county surplus records so we can invite them to claim (skip tracing).

For each record we check at most four places, in order, and stop as soon as one gives a usable way
to reach the person:

1. Surpay itself: is the owner already a verified user? (They get an in-app notice.)
2. The county's list: the owner's address as published (often the sold property; USPS forwards mail
   for a year after a move).
3. A web search for the name and city, through a search engine's official API (Google Programmable
   Search or Brave). Profiles (LinkedIn, Facebook) and people-search pages found are saved as links
   for staff to open by hand: we don't scrape those sites, which their terms forbid.
4. An obituary search: if the owner has died, the money goes to their heirs, so staff look for family.

Each run records every place checked and what it found, then moves on to the next record. For records
not found, staff get one-click links to search further by hand (manual_sources), and can add what
they find.

Outreach is by mailed letter, email (with an unsubscribe link) or in-app notice. No automated calls or
texts (TCPA). Every lookup and message is in the audit trail; anyone can opt out.
"""

import re
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .models import OwnerContact, SurplusRecord, TraceRun, User

MAX_STEPS = 4
BUSINESS_WORDS = {"llc", "inc", "corp", "corporation", "co", "company", "trust", "bank", "church", "lp", "ltd",
                  "holdings", "properties", "property", "investments", "investment", "association", "assn", "partners",
                  "ministries", "county", "city", "state", "group", "realty", "enterprises", "mortgage", "fund", "llp"}
PEOPLE_SEARCH = ("whitepages.com", "truepeoplesearch.com", "fastpeoplesearch.com", "spokeo.com", "beenverified.com",
                 "radaris.com", "peoplefinders.com", "thatsthem.com", "searchpeoplefree.com", "clustrmaps.com",
                 "fastbackgroundcheck.com", "nuwber.com", "usphonebook.com")
PROFILE_SITES = ("linkedin.com/in", "facebook.com", "instagram.com", "x.com", "twitter.com")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b")
_ADDR = re.compile(r",\s*([A-Za-z .'-]+),?\s+([A-Z]{2})\b")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Who and where ------------------------------------------------------------------------------

def person_name(owner: str) -> tuple[str | None, bool]:
    """('Jordan A Testwell', deceased?) from a county's owner text, or (None, ...) for a business.

    'TESTWELL, JORDAN A' -> 'Jordan A Testwell'; 'ESTATE OF MARY PARENT' -> ('Mary Parent', True);
    'JOHN DOE AND JANE DOE' -> 'John Doe'; 'ACME HOLDINGS LLC' -> None.
    """
    s = re.sub(r"\s+", " ", owner or "").strip(" ,.")
    deceased = bool(re.search(r"\b(estate of|est of|deceased|heirs of|unknown heirs)\b", s, re.I))
    s = re.sub(r"\b(the )?(estate of|est of|heirs of|unknown heirs( of)?|deceased|et al|etal|etux|et ux|et vir)\b", " ", s, flags=re.I)
    first, *rest = re.split(r"\s+(?:&|and)\s+|/|;", s, maxsplit=1, flags=re.I)
    # "MORGAN & RILEY EXAMPLE": a couple sharing the surname at the end -> "Morgan Example".
    if rest and len(first.split()) == 1 and "," not in first and len(rest[0].split()) >= 2:
        first = f"{first} {rest[0].split()[-1]}"
    s = first
    words = re.findall(r"[A-Za-z'-]+", s.lower())
    if not words or any(w in BUSINESS_WORDS for w in words):
        return None, deceased
    if "," in s:
        last, _, first = s.partition(",")
        s = f"{first} {last}"
    parts = [p for p in re.findall(r"[A-Za-z'-]+", s) if p.lower() not in {"mr", "mrs", "ms", "dr", "jr", "sr", "ii", "iii"}]
    if len(parts) < 2:
        return None, deceased
    return " ".join(p.capitalize() for p in parts), deceased


def place(r: SurplusRecord) -> tuple[str, str]:
    """(city, state) from the owner's address on the list, else the county."""
    m = _ADDR.search(r.owner_address or "")
    if m and "county" not in m.group(1).lower():
        return m.group(1).strip().title(), m.group(2)
    return f"{r.county} County", r.state


# --- Search engine (official APIs only) ---------------------------------------------------------------

def search_ready() -> str:
    if config.GOOGLE_CSE_KEY and config.GOOGLE_CSE_ID:
        return "google"
    if config.BRAVE_API_KEY:
        return "brave"
    return ""


def web_search(query: str) -> list[dict]:
    """[{title, url, snippet}] from the configured search API; [] if none is configured."""
    provider = search_ready()
    try:
        if provider == "google":
            r = httpx.get("https://www.googleapis.com/customsearch/v1", timeout=20,
                          params={"key": config.GOOGLE_CSE_KEY, "cx": config.GOOGLE_CSE_ID, "q": query, "num": 10})
            r.raise_for_status()
            return [{"title": i.get("title", ""), "url": i.get("link", ""), "snippet": i.get("snippet", "")}
                    for i in r.json().get("items", [])]
        if provider == "brave":
            r = httpx.get("https://api.search.brave.com/res/v1/web/search", timeout=20,
                          headers={"X-Subscription-Token": config.BRAVE_API_KEY, "Accept": "application/json"},
                          params={"q": query, "count": 10})
            r.raise_for_status()
            return [{"title": i.get("title", ""), "url": i.get("url", ""), "snippet": i.get("description", "")}
                    for i in r.json().get("web", {}).get("results", [])]
    except httpx.HTTPError:
        return []
    return []


def _mentions(text: str, name: str) -> bool:
    t = text.lower()
    parts = name.lower().split()
    return parts[0] in t and parts[-1] in t


def classify(results: list[dict], name: str, city: str, state: str) -> list[dict]:
    """Turn search results about this person into contact leads."""
    leads = []
    for res in results:
        text = f"{res['title']} {res['snippet']}"
        if not _mentions(text, name):
            continue
        url = res["url"]
        host = urlparse(url).netloc.lower().removeprefix("www.")
        local = city.lower().replace(" county", "") in text.lower() or f" {state.lower()}" in f" {text.lower()}"
        conf = "medium" if local else "low"
        if "obituar" in url.lower() or "obituar" in text.lower() or host in ("legacy.com", "tributearchive.com"):
            leads.append({"kind": "obituary", "value": url, "label": res["title"][:200], "confidence": conf,
                          "note": res["snippet"][:300]})
        elif any(s in url.lower() for s in PROFILE_SITES):
            leads.append({"kind": "profile", "value": url, "label": res["title"][:200], "confidence": conf,
                          "note": "Open by hand and send a message through the site if it's the right person."})
        elif any(host.endswith(p) for p in PEOPLE_SEARCH):
            leads.append({"kind": "link", "value": url, "label": f"People-search page: {res['title'][:150]}",
                          "confidence": "low", "note": "Open by hand: may list a current address and phone."})
        for email in _EMAIL.findall(res["snippet"]):
            if name.split()[-1].lower() in email.lower():
                leads.append({"kind": "email", "value": email, "label": "Email in search result", "confidence": conf,
                              "note": url})
    return leads


# --- Running a trace ------------------------------------------------------------------------------------

def _verified_users(session: Session) -> list[User]:
    from .models import IdentityVerification
    return list(session.scalars(select(User).join(IdentityVerification).where(
        IdentityVerification.review_status == "approved", User.suspended_at.is_(None))))


def surpay_user_for(session: Session, r: SurplusRecord, users: list[User] | None = None) -> User | None:
    from .matching import find_all_matches
    for u in users if users is not None else _verified_users(session):
        if any(m.record.id == r.id for m in find_all_matches(session, u)):
            return u
    return None


def _add(session: Session, r: SurplusRecord, source: str, lead: dict, url: str = "") -> OwnerContact:
    existing = [c for c in session.scalars(select(OwnerContact).where(OwnerContact.record_id == r.id))
                if c.kind == lead["kind"] and c.value == lead["value"]]
    if existing:
        return existing[0]
    c = OwnerContact(record_id=r.id, kind=lead["kind"], value=lead["value"], label=lead.get("label", ""),
                     source=source, source_url=url or lead.get("source_url", ""), confidence=lead.get("confidence", "low"),
                     note=lead.get("note", ""))
    session.add(c)
    return c


def trace(session: Session, r: SurplusRecord, by: str = "system", users: list[User] | None = None) -> TraceRun:
    """Check up to four places for this record's owner, record what each found, and stop early on a hit."""
    run = TraceRun(record_id=r.id, status="not_found", steps=[], by=by, started_at=_now())
    session.add(run)
    name, deceased = person_name(r.owner_name)
    city, state = place(r)
    steps: list[dict] = []
    usable = False

    # 1. Already one of our verified users?
    user = surpay_user_for(session, r, users)
    steps.append({"source": "Surpay users", "query": r.owner_name, "found": user is not None,
                  "note": f"Matches {user.app_number}" if user else "No verified user matches this record"})
    if user is not None:
        _add(session, r, "surpay_user", {"kind": "user", "value": user.app_number or str(user.id),
                                         "label": user.full_name, "confidence": "high",
                                         "note": "Verified Surpay user: notified in the app"})
        from .models import Notification
        session.add(Notification(user_id=user.id, kind="new_match", title="We found money that may be yours",
                                 body=f"Funds held by {r.county} County, {r.state} ({r.reference}). Open My money."))
        run.status, usable = "user_found", True

    # 2. The address on the county's list.
    if not usable:
        has = bool(r.owner_address and len(r.owner_address) > 8)
        steps.append({"source": "County list address", "query": r.reference, "found": has,
                      "note": r.owner_address if has else "The list has no owner address"})
        if has:
            _add(session, r, "county_list", {"kind": "address", "value": r.owner_address, "label": r.owner_name,
                                             "confidence": "low",
                                             "note": "Address on the county's list: often the sold property, so "
                                                     "mail may only arrive if it's forwarded."})

    if not usable and name is None:
        steps.append({"source": "Web search", "query": r.owner_name, "found": False,
                      "note": "Owner is a business or the name can't be read: search the state business registry"})
        run.status = "business"
    elif not usable:
        provider = search_ready()
        # 3. Web search for the person.
        q1 = f'"{name}" {city} {state}'
        found = classify(web_search(q1), name, city, state) if provider else []
        steps.append({"source": f"Web search ({provider or 'not set up'})", "query": q1, "found": bool(found),
                      "note": f"{len(found)} lead(s)" if provider else "Add a Google or Brave search API key to search the web"})
        for lead in found:
            _add(session, r, "web_search", lead)
        usable = any(lead["kind"] == "email" and lead["confidence"] != "low" for lead in found)
        # 4. Obituary search: if they died, the money goes to heirs.
        if not usable:
            q2 = f'"{name}" obituary {state}'
            obits = [x for x in (classify(web_search(q2), name, city, state) if provider else []) if x["kind"] == "obituary"]
            steps.append({"source": f"Obituary search ({provider or 'not set up'})", "query": q2, "found": bool(obits),
                          "note": "Possible obituary: look for heirs" if obits else ("No obituary found" if provider else "Not set up")})
            for lead in obits:
                _add(session, r, "obituary_search", lead)
            deceased = deceased or any(o["confidence"] == "medium" for o in obits)
        if usable:
            run.status = "found"
        elif any(s["found"] for s in steps[1:]):
            run.status = "leads"

    run.deceased = deceased
    run.steps = steps[:MAX_STEPS]
    run.finished_at = _now()
    return run


def queue(session: Session, limit: int = 25, min_cents: int = 0) -> list[SurplusRecord]:
    """Listed records nobody has traced yet, biggest first (records past their deadline are skipped)."""
    from .legal import record_deadline
    traced = select(TraceRun.record_id)
    rows = session.scalars(select(SurplusRecord).where(
        SurplusRecord.status == "listed", SurplusRecord.amount_cents >= min_cents, SurplusRecord.id.not_in(traced))
        .order_by(SurplusRecord.amount_cents.desc()).limit(limit * 3)).all()
    return [r for r in rows if record_deadline(r)["urgency"] != "expired"][:limit]


def trace_batch(session: Session, limit: int = 25, min_cents: int = 0) -> list[TraceRun]:
    users = _verified_users(session)
    runs = [trace(session, r, users=users) for r in queue(session, limit, min_cents)]
    session.commit()
    return runs


def summary(session: Session, demo_only: bool = False) -> dict:
    stmt = select(TraceRun.status, func.count()).group_by(TraceRun.status)
    if demo_only:
        stmt = stmt.join(SurplusRecord).where(SurplusRecord.source == "demo")
    counts = dict(session.execute(stmt).all())
    listed = select(func.count()).select_from(SurplusRecord).where(SurplusRecord.status == "listed")
    traced = session.scalar(select(func.count(func.distinct(TraceRun.record_id))))
    return {"by_status": counts, "listed": session.scalar(listed), "traced": traced,
            "search_provider": search_ready() or None}


# --- Where else to look (by hand) ------------------------------------------------------------------------------

def manual_sources(r: SurplusRecord, list_page: str = "") -> list[dict]:
    """Links staff can open to keep looking, with what each is good for."""
    name, _ = person_name(r.owner_name)
    who = name or r.owner_name.title()
    first, last = (who.split()[0], who.split()[-1]) if name else ("", "")
    city, state = place(r)
    g = lambda q: f"https://www.google.com/search?q={quote_plus(q)}"  # noqa: E731
    out = [
        {"name": "Google", "url": g(f'"{who}" {city} {state}'), "why": "Any mention: news, workplace, social profiles"},
        {"name": "Google: obituary", "url": g(f'"{who}" obituary {state}'), "why": "If they died, the obituary names the family (heirs)"},
        {"name": "Legacy.com obituaries", "url": f"https://www.legacy.com/us/obituaries/name/{quote_plus(last.lower())}/{quote_plus(first.lower())}" if name else "https://www.legacy.com/obituaries/search",
         "why": "Largest obituary database"},
        {"name": "LinkedIn people search", "url": f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(who)}",
         "why": "Sign in to LinkedIn; message them through the site"},
        {"name": "Facebook people search", "url": f"https://www.facebook.com/search/people/?q={quote_plus(who)}",
         "why": "Match by city and photo; message through the site"},
        {"name": "TruePeopleSearch", "url": f"https://www.truepeoplesearch.com/results?name={quote_plus(who)}&citystatezip={quote_plus(state)}",
         "why": "Current address, phones and relatives (public records)"},
        {"name": "Whitepages", "url": f"https://www.whitepages.com/name/{quote_plus(who.replace(' ', '-'))}/{quote_plus(state)}",
         "why": "Current address and landline"},
        {"name": "Google: probate", "url": g(f'"{who}" probate {r.county} County {state}'), "why": "An estate case names the administrator"},
        {"name": "Missing Money (state unclaimed property)", "url": "https://www.missingmoney.com/",
         "why": "If they've claimed other unclaimed money, the state may have a newer address"},
    ]
    if name is None:
        out.insert(0, {"name": "Google: business registry", "url": g(f'"{r.owner_name}" {state} secretary of state business search'),
                       "why": "Find the company's registered agent and officers"})
    if list_page:
        out.append({"name": "The county's list page", "url": list_page, "why": "Check the record is still listed and who to call"})
    return out
