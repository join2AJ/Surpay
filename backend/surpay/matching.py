"""Find surplus records that plausibly belong to a user."""

from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import SurplusRecord, User
from .normalize import name_tokens, normalize_street, split_street_number

STRONG, LIKELY, POSSIBLE = "strong", "likely", "possible"


@dataclass
class Match:
    record: SurplusRecord
    confidence: str
    name_score: float
    address_matched: bool


def _name_score(user_name: str, record_name: str) -> float:
    """0-100. Requires the user's first and last name to both appear in the owner field.

    Owner fields often list several people ("JOHN & MARY SMITH"), so we compare the user's
    first/last pair against every token rather than the whole string.
    """
    u = name_tokens(user_name)
    r = name_tokens(record_name)
    if len(u) < 2 or not r:
        return 0.0
    first, last = u[0], u[-1]

    def best(token: str) -> float:
        return max(fuzz.ratio(token, t) for t in r)

    last_score = best(last)
    first_score = best(first)
    # Allow an initial in the record ("J SMITH") to stand in for the first name.
    if first_score < 90 and any(len(t) == 1 and t == first[0] for t in r):
        first_score = 85.0
    if last_score < 85 or first_score < 80:
        return 0.0
    return round(0.6 * last_score + 0.4 * first_score, 1)


def _address_matches(user: User, record: SurplusRecord) -> bool:
    rec = normalize_street(record.owner_address)
    for addr in user.addresses:
        if addr.state.upper() != record.state:
            continue
        number, street = split_street_number(addr.street)
        if not number or not street:
            continue
        if f"{number} " in f"{rec} " and fuzz.partial_ratio(street, rec) >= 85:
            return True
    return False


def find_matches(session: Session, user: User) -> list[Match]:
    # Only the person's own names: the name on their ID once submitted, plus other names they
    # declared before submitting. This stops anyone searching for someone else.
    own = user.identity.legal_name if user.identity is not None else user.full_name
    names = [own, *[n for n in (user.other_names or []) if n]]
    surnames = {name_tokens(n)[-1] for n in names if len(name_tokens(n)) >= 2}
    if not surnames:
        return []

    # Cheap candidate filter on the surname prefix (first 4 letters) to tolerate typos at
    # the end of a name; the scoring below does the real work.
    candidates = session.scalars(
        select(SurplusRecord).where(
            SurplusRecord.status == "listed",
            or_(*[SurplusRecord.owner_name_norm.contains(s[:4]) for s in surnames]),
        )
    ).all()

    matches = []
    for rec in candidates:
        score = max(_name_score(n, rec.owner_name) for n in names)
        if score == 0:
            continue
        addr = _address_matches(user, rec)
        if addr and score >= 85:
            conf = STRONG
        elif score >= 95:
            conf = LIKELY
        elif score >= 85:
            conf = POSSIBLE
        else:
            continue
        matches.append(Match(rec, conf, score, addr))

    order = {STRONG: 0, LIKELY: 1, POSSIBLE: 2}
    matches.sort(key=lambda m: (order[m.confidence], -m.record.amount_cents))
    return matches
