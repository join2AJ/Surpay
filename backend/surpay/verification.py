"""Two-factor confirmation before signing: a 6-digit code to the user's email and one to their phone.

Codes are stored hashed, expire after 10 minutes and allow 5 tries. A signature needs both channels
confirmed within the last 30 minutes; the signed document records when each was confirmed.
"""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config, delivery
from .models import OneTimeCode, User

CODE_MINUTES = 10
MAX_ATTEMPTS = 5
MAX_PER_HOUR = 5
FRESH_MINUTES = 30
CHANNELS = ("email", "phone")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def _hash(user_id: int, code: str) -> str:
    return hmac.new(config.SECRET_KEY.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def phone_of(user: User) -> str:
    raw = (user.identity.phone if user.identity is not None and user.identity.phone else user.phone) or ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return ("+" + digits) if digits else ""


def mask(channel: str, destination: str) -> str:
    if channel == "email":
        name, _, domain = destination.partition("@")
        return f"{name[:1]}•••@{domain}"
    return f"•••{destination[-4:]}" if destination else ""


def destination(user: User, channel: str) -> str:
    if channel == "email":
        return user.email
    return phone_of(user)


def start(session: Session, user: User, channel: str) -> dict:
    if channel not in CHANNELS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose email or phone")
    to = destination(user, channel)
    if not to:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add your mobile number to your profile first")
    recent = session.scalar(select(func.count()).select_from(OneTimeCode).where(
        OneTimeCode.user_id == user.id, OneTimeCode.channel == channel,
        OneTimeCode.created_at > _now() - timedelta(hours=1))) or 0
    if recent >= MAX_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes. Try again in an hour.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(OneTimeCode(user_id=user.id, channel=channel, destination=to, code_hash=_hash(user.id, code),
                            expires_at=_now() + timedelta(minutes=CODE_MINUTES)))
    text = f"Your {config.COMPANY_NAME} code is {code}. It expires in {CODE_MINUTES} minutes. Never share it."
    sent = (delivery.send_email(to, f"{config.COMPANY_NAME} code: {code}", text) if channel == "email"
            else delivery.send_sms(to, text))
    out = {"channel": channel, "sent_to": mask(channel, to), "sent": sent, "expires_in_minutes": CODE_MINUTES}
    if not sent:
        demo = user.email.endswith("@surpay.test")
        if config.TEST_SERVER or demo:
            # A test server can't deliver codes, so it shows them; a real server never does.
            out["test_code"] = code
        else:
            session.rollback()
            what = "Email" if channel == "email" else "Text-message"
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                f"{what} codes aren't available right now. Please try again later.")
    return out


def confirm(session: Session, user: User, channel: str, code: str) -> dict:
    row = session.scalars(select(OneTimeCode).where(
        OneTimeCode.user_id == user.id, OneTimeCode.channel == channel, OneTimeCode.verified_at.is_(None))
        .order_by(OneTimeCode.id.desc()).limit(1)).first()
    if row is None or _aware(row.expires_at) < _now():
        raise HTTPException(status.HTTP_409_CONFLICT, "That code has expired. Ask for a new one.")
    if row.attempts >= MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong tries. Ask for a new code.")
    row.attempts += 1
    if not hmac.compare_digest(row.code_hash, _hash(user.id, code.strip())):
        session.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That code isn't right")
    row.verified_at = _now()
    if channel == "email":
        user.email_verified_at = row.verified_at
    else:
        user.phone_verified_at = row.verified_at
    return state(session, user)


def _last(session: Session, user: User, channel: str) -> OneTimeCode | None:
    return session.scalars(select(OneTimeCode).where(
        OneTimeCode.user_id == user.id, OneTimeCode.channel == channel, OneTimeCode.verified_at.is_not(None))
        .order_by(OneTimeCode.verified_at.desc()).limit(1)).first()


def state(session: Session, user: User) -> dict:
    out = {}
    for ch in CHANNELS:
        last = _last(session, user, ch)
        at = _aware(last.verified_at) if last else None
        out[ch] = {"destination": mask(ch, destination(user, ch)), "verified_at": at,
                   "fresh": at is not None and at > _now() - timedelta(minutes=FRESH_MINUTES)}
    out["ready_to_sign"] = all(out[ch]["fresh"] for ch in CHANNELS)
    return out


def require_fresh(session: Session, user: User) -> dict:
    """Both codes confirmed in the last 30 minutes, or 403. Returns the evidence for the record."""
    s = state(session, user)
    if not s["ready_to_sign"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Confirm the codes we send to your email and phone before signing")
    return {"email": destination(user, "email"), "email_verified_at": s["email"]["verified_at"],
            "phone": destination(user, "phone"), "phone_verified_at": s["phone"]["verified_at"]}
