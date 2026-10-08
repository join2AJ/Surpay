"""In-app messages between a claimant and their attorney.

Rules: the attorney writes first; contact details (phone numbers, email addresses, links,
other messaging apps) can't be sent, so the conversation stays in the app where it is
recorded; both sides agree to the code of conduct.
"""

import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Claim, Message, Notification, User

CODE_OF_CONDUCT = [
    "Keep every conversation in the Surpay app. Don't ask for or share phone numbers, email "
    "addresses, social media, links or other apps.",
    "Talk only about this claim. Be respectful and professional.",
    "Attorneys: follow your state's Rules of Professional Conduct, including confidentiality and "
    "communication duties. Never ask the client for payment outside the agreement.",
    "Clients: never send passwords, full Social Security numbers or bank details in chat. Upload "
    "documents only through the app.",
    "Messages are encrypted, kept as part of the case record, and may be reviewed by Surpay to "
    "resolve a dispute or a report of misuse.",
]

_BLOCKED = [
    (re.compile(r"\(?\b\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}\b"), "phone numbers"),
    (re.compile(r"\+\d[\d\s\-().]{7,}\d"), "phone numbers"),
    (re.compile(r"\d{10,}"), "phone numbers"),
    (re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+"), "email addresses"),
    (re.compile(r"\b[\w.\-]+\s*(?:\(at\)|\[at\]| at )\s*[\w\-]+\s*(?:\.|\(dot\)|\[dot\]| dot )\s*(?:com|net|org|co|us|in)\b",
                re.I), "email addresses"),
    (re.compile(r"(?:https?://|www\.)\S+", re.I), "links"),
    (re.compile(r"\b[\w\-]+\.(?:com|net|org|io|me|co|us|app|info|biz|ly)\b", re.I), "links"),
    (re.compile(r"\b(?:whats\s*app|telegram|signal app|wechat|instagram|insta|facebook|messenger|snapchat|"
                r"skype|zoom|google meet|text me|call me|my cell|my number)\b", re.I), "other contact methods"),
]


def blocked_reason(body: str) -> str | None:
    found = sorted({label for pattern, label in _BLOCKED if pattern.search(body)})
    if not found:
        return None
    return (f"For everyone's safety, messages can't include {' or '.join(found)}. Please keep the "
            "conversation in the Surpay app.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def thread_open(claim: Claim) -> bool:
    return claim.attorney_id is not None and claim.assignment_status == "accepted"


def send(session: Session, claim: Claim, sender: User, role: str, body: str) -> Message:
    body = body.strip()
    if not body:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Type a message")
    if not thread_open(claim):
        raise HTTPException(status.HTTP_409_CONFLICT, "Messages open once an attorney accepts the case")
    if role == "claimant" and not any(m.sender_role == "attorney" for m in claim.messages):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Your attorney will send the first message. You can reply after that.")
    if (reason := blocked_reason(body)) is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, reason)
    msg = Message(claim_id=claim.id, sender_id=sender.id, sender_role=role, body=body, created_at=_now())
    claim.messages.append(msg)
    recipient = claim.attorney_id if role == "claimant" else claim.user_id
    who = "Your client" if role == "claimant" else "Your attorney"
    session.add(Notification(user_id=recipient, kind="message", title=f"New message from {who.lower()}",
                             body=body[:140], claim_id=claim.id))
    return msg


def mark_read(claim: Claim, reader_role: str) -> None:
    for m in claim.messages:
        if m.sender_role != reader_role and m.read_at is None:
            m.read_at = _now()


def message_out(m: Message) -> dict:
    return {"id": m.id, "sender_role": m.sender_role, "body": m.body, "created_at": m.created_at,
            "read": m.read_at is not None}
