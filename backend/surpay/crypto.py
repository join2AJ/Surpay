"""Encrypt sensitive files (ID photos, selfies) before they go into the database."""

import base64
import hashlib

from cryptography.fernet import Fernet

from . import config


def _fernet() -> Fernet:
    key = hashlib.sha256(config.ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt(token: bytes) -> bytes:
    return _fernet().decrypt(token)
