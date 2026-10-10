"""Application-level encryption for sensitive data stored in the database.

ID photos, selfies, signatures, chat messages and identity details (date of birth, SSN digits,
phone, home address) are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before they reach
the database, on top of the database provider's own disk encryption.

Key rotation: set the new key as SURPAY_ENCRYPTION_KEY and the old one as
SURPAY_ENCRYPTION_KEY_OLD. New data uses the new key; old data still opens, and
`python -m surpay.cli rotate-keys` re-encrypts it so the old key can then be removed.
"""

import base64
import hashlib
from datetime import date

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from . import config


def _key(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def _fernet() -> MultiFernet:
    # Newest first. SECRET_KEY stays as a last fallback because it was the encryption key until
    # SURPAY_ENCRYPTION_KEY was set: data stored before then still opens, and `rotate-keys`
    # re-encrypts it under the current key.
    secrets_ = []
    for k in (config.ENCRYPTION_KEY, config.ENCRYPTION_KEY_OLD, config.SECRET_KEY):
        if k and k not in secrets_:
            secrets_.append(k)
    return MultiFernet([_key(k) for k in secrets_])


def encrypt(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def rotate(token: bytes) -> bytes:
    return _fernet().rotate(token)


def is_token(value: str) -> bool:
    # Every Fernet token starts with version byte 0x80, which base64-encodes to "gAAAAA".
    return value.startswith("gAAAAA")


def sha256_hex(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


class EncryptedText(TypeDecorator):
    """A text column stored encrypted. Rows written before encryption was added still read."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(str(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not is_token(value):
            return value  # legacy plaintext; re-encrypted by init_db
        try:
            return decrypt(value.encode()).decode()
        except InvalidToken:
            raise RuntimeError(
                "Stored data can't be decrypted with the configured keys. If SURPAY_ENCRYPTION_KEY was changed, "
                "set the previous value as SURPAY_ENCRYPTION_KEY_OLD.") from None


class EncryptedDate(EncryptedText):
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return super().process_bind_param(value.isoformat() if isinstance(value, date) else value, dialect)

    def process_result_value(self, value, dialect):
        text = super().process_result_value(value, dialect)
        return date.fromisoformat(text[:10]) if text else None


def _current_only() -> Fernet:
    return _key(config.ENCRYPTION_KEY)


def needs_rotation(token: bytes | str) -> bool:
    try:
        _current_only().decrypt(token.encode() if isinstance(token, str) else token)
        return False
    except InvalidToken:
        return True


def rotate_all(session) -> int:
    """Re-encrypt values not yet under the current key. Safe to run on every start; returns rows changed."""
    from sqlalchemy import LargeBinary, select, text
    from sqlalchemy.orm.attributes import flag_modified

    from . import models

    changed = 0
    for model in (models.IdentityVerification, models.AttorneyProfile, models.Relative, models.Agreement,
                  models.Message, models.StaffNote, models.DocumentRequest):
        table = model.__table__
        cols = [c for c in table.columns if isinstance(c.type, (LargeBinary, EncryptedText))]
        names = ", ".join(c.name for c in cols)
        stale = [row[0] for row in session.execute(text(f"SELECT id, {names} FROM {table.name}"))
                 if any(v is not None and (not isinstance(v, str) or is_token(v)) and needs_rotation(v)
                        for v in row[1:])]
        for obj in session.scalars(select(model).where(model.id.in_(stale))) if stale else []:
            for c in cols:
                value = getattr(obj, c.key)
                if value is None:
                    continue
                if isinstance(c.type, LargeBinary):
                    setattr(obj, c.key, rotate(value))
                else:
                    flag_modified(obj, c.key)  # written back with the current key
            changed += 1
    session.commit()
    return changed
