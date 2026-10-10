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
    return crypto.encrypt(clean_image(data, label))


def clean_image(data: bytes, label: str) -> bytes:
    """Re-encode the photo: drops hidden metadata (GPS location, device serials) and anything
    that isn't really an image."""
    import io

    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)  # keep it the right way up once EXIF is gone
            if img.width * img.height > 40_000_000:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{label}: image is too large")
            out = io.BytesIO()
            img.convert("RGB").save(out, format="JPEG", quality=90)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{label}: couldn't read this photo, please retake it") from None


class AdminScope:
    """Who is using the staff dashboard: real staff (everything) or the demo admin (demo data only)."""

    def __init__(self, demo: bool):
        self.demo = demo

    def check(self, allowed: bool) -> None:
        """404 for anything outside the demo when signed in as the demo admin."""
        if self.demo and not allowed:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not available in the admin demo")

    def read_only(self) -> None:
        if self.demo:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Read-only in the admin demo")


DEMO_ADMIN_HOURS = 2


def demo_admin_token() -> str:
    import jwt
    from datetime import datetime, timedelta, timezone
    exp = datetime.now(timezone.utc) + timedelta(hours=DEMO_ADMIN_HOURS)
    return jwt.encode({"scope": "demo_admin", "exp": exp}, config.SECRET_KEY, algorithm="HS256")


def _is_demo_admin_token(token: str) -> bool:
    import jwt
    try:
        return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"]).get("scope") == "demo_admin"
    except jwt.PyJWTError:
        return False


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> AdminScope:
    if config.ADMIN_TOKEN and x_admin_token and hmac.compare_digest(x_admin_token, config.ADMIN_TOKEN):
        return AdminScope(demo=False)
    if config.DEMO_ENABLED and x_admin_token and _is_demo_admin_token(x_admin_token):
        return AdminScope(demo=True)
    if not config.ADMIN_TOKEN and not config.DEMO_ENABLED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong admin token")


Admin = Annotated[AdminScope, Depends(require_admin)]


def client_ip(request: Request) -> str:
    """The address that connected to our hosting provider's edge.

    Render's proxy appends the real peer to X-Forwarded-For, so the rightmost entry is the one
    a client can't forge (anything to its left is whatever the client sent).
    """
    forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if forwarded:
        # SURPAY_PROXY_HOPS: how many proxies we sit behind (each appends one entry).
        return forwarded[max(0, len(forwarded) - config.PROXY_HOPS)][:64]
    return request.client.host if request.client else ""


def client_info(request: Request) -> ClientInfo:
    """IP address and device details for the audit trail. The app sends the X-Device-* headers."""
    h = request.headers
    device = " / ".join(x for x in (h.get("x-device-model", ""), h.get("x-os-version", ""),
                                     h.get("x-app-version", "")) if x)
    install = h.get("x-install-id", "")
    device_id = h.get("x-device-id", "")
    return ClientInfo(
        ip=client_ip(request),
        user_agent=h.get("user-agent", ""),
        device_id=f"{device_id}/{install}" if install else device_id,
        device_info=device,
    )


Client = Annotated[ClientInfo, Depends(client_info)]
