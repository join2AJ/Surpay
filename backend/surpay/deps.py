"""Request dependencies shared by every router."""

import base64
import binascii
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import config, crypto
from .auth import current_user
from .db import get_session
from .models import User

DbSession = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(current_user)]


_MAX_IMAGE_BYTES = 6 * 1024 * 1024


def encrypt_image(b64: str, label: str) -> bytes:
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{label}: not a valid image") from None
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{label}: image is too large (max 6 MB)")
    if not (data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{label}: must be a JPEG or PNG photo")
    return crypto.encrypt(data)


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    if not config.ADMIN_TOKEN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong admin token")


Admin = Annotated[None, Depends(require_admin)]
