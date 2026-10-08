"""Request dependencies shared by every router."""

import base64
import binascii
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import config, crypto
from .audit import ClientInfo
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


def client_info(request: Request) -> ClientInfo:
    """IP address and device details for the audit trail. The app sends the X-Device-* headers."""
    h = request.headers
    device = " / ".join(x for x in (h.get("x-device-model", ""), h.get("x-os-version", ""),
                                     h.get("x-app-version", "")) if x)
    install = h.get("x-install-id", "")
    device_id = h.get("x-device-id", "")
    return ClientInfo(
        ip=request.client.host if request.client else "",
        user_agent=h.get("user-agent", ""),
        device_id=f"{device_id}/{install}" if install else device_id,
        device_info=device,
    )


Client = Annotated[ClientInfo, Depends(client_info)]
