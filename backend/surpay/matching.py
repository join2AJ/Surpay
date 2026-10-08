"""Find surplus records that plausibly belong to a user."""

from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import PreviousAddress, Relative, SurplusRecord, User
from .normalize import name_tokens, normalize_street, split_street_number

STRONG, LIKELY, POSSIBLE = "strong", "likely", "possible"


@dataclass
class Match:
    record: SurplusRecord
    confidence: str
    name_score: float
    address_matched: bool
    # Set when this is a family member's record that the user claims as heir / under authority.
    relative: Relative | None = field(default=None)


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


def _address_matches(addresses: list[PreviousAddress], record: SurplusRecord) -> bool:
    rec = normalize_street(record.owner_address)
    for addr in addresses:
        if addr.state.upper() != record.state:
            continue
        number, street = split_street_number(addr.street)
        if not number or not street:
            continue
        if f"{number} " in f"{rec} " and fuzz.partial_ratio(street, rec) >= 85:
            return True
    return False


def match_names(session: Session, names: list[str], addresses: list[PreviousAddress]) -> list[Match]:
    names = [n for n in names if n]
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
        addr = _address_matches(addresses, rec)
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


def find_matches(session: Session, user: User) -> list[Match]:
    """Records in the person's own name.

    Only their own names: the name on their ID once submitted, plus other names they declared
    before submitting. This stops anyone searching for someone else.
    """
    own = user.identity.legal_name if user.identity is not None else user.full_name
    return match_names(session, [own, *(user.other_names or [])], user.own_addresses)


def find_relative_matches(session: Session, user: User, relative: Relative) -> list[Match]:
    homes = [a for a in user.addresses if a.relative_id == relative.id]
    found = match_names(session, [relative.full_name, *(relative.other_names or [])], homes)
    for m in found:
        m.relative = relative
    return found


def find_all_matches(session: Session, user: User) -> list[Match]:
    """Own records, then those of family members whose relationship staff have verified."""
    out = find_matches(session, user)
    seen = {m.record.id for m in out}
    for rel in user.relatives:
        if rel.review_status != "approved":
            continue
        for m in find_relative_matches(session, user, rel):
            if m.record.id not in seen:
                seen.add(m.record.id)
                out.append(m)
    return out
