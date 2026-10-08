"""Tamper-evident audit trail.

Every significant action (sign-up, consent, ID submission, signing, status changes, staff
decisions, messages, data exports) is written here with the time, the account, the IP address
and the device it came from. Each entry includes the hash of the one before it, so changing or
removing any past entry is detectable with `verify()`.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .crypto import sha256_hex
from .models import AuditLog


@dataclass(frozen=True)
class ClientInfo:
    """Where a request came from: network address and the phone that sent it."""
    ip: str = ""
    user_agent: str = ""
    device_id: str = ""
    device_info: str = ""


SYSTEM = ClientInfo()


def _stamp(at: datetime) -> str:
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)  # SQLite drops the timezone
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _digest(prev_hash: str, e: AuditLog) -> str:
    body = json.dumps({
        "at": _stamp(e.at), "actor_type": e.actor_type, "actor_id": e.actor_id, "action": e.action,
        "entity_type": e.entity_type, "entity_id": e.entity_id, "ip": e.ip_address,
        "user_agent": e.user_agent, "device_id": e.device_id, "device_info": e.device_info,
        "details": e.details or {},
    }, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_hex(prev_hash + body)


def record(session: Session, action: str, *, actor_type: str = "user", actor_id: int | None = None,
           entity_type: str = "", entity_id: int | None = None, client: ClientInfo = SYSTEM,
           details: dict | None = None) -> AuditLog:
    """Add an entry to the chain. It's saved with the caller's transaction."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(727377)"))  # one writer extends the chain at a time
    session.flush()
    prev = session.scalar(select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)) or ""
    entry = AuditLog(
        at=datetime.now(timezone.utc), actor_type=actor_type, actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id, ip_address=client.ip[:64],
        user_agent=client.user_agent[:255], device_id=client.device_id[:128],
        device_info=client.device_info[:255], details=details or {}, prev_hash=prev,
    )
    entry.hash = _digest(prev, entry)
    session.add(entry)
    return entry


def verify(session: Session) -> dict:
    """Recompute the whole chain. Returns the first broken entry, if any."""
    prev = ""
    count = 0
    for e in session.scalars(select(AuditLog).order_by(AuditLog.id)):
        if e.prev_hash != prev or e.hash != _digest(prev, e):
            return {"ok": False, "entries": count, "broken_at": e.id}
        prev = e.hash
        count += 1
    return {"ok": True, "entries": count, "broken_at": None, "head": prev}


def entry_out(e: AuditLog) -> dict:
    return {"id": e.id, "at": _stamp(e.at), "actor_type": e.actor_type, "actor_id": e.actor_id,
            "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id,
            "ip": e.ip_address, "user_agent": e.user_agent, "device_id": e.device_id,
            "device_info": e.device_info, "details": e.details or {}, "hash": e.hash}
