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
    keys = [_key(config.ENCRYPTION_KEY)]
    if config.ENCRYPTION_KEY_OLD:
        keys.append(_key(config.ENCRYPTION_KEY_OLD))
    return MultiFernet(keys)


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
            return value


class EncryptedDate(EncryptedText):
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return super().process_bind_param(value.isoformat() if isinstance(value, date) else value, dialect)

    def process_result_value(self, value, dialect):
        text = super().process_result_value(value, dialect)
        return date.fromisoformat(text[:10]) if text else None
