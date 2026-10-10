from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .db import get_session
from .models import User

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=config.TOKEN_TTL_DAYS)
    payload = {"sub": str(user.id), "v": user.token_version or 0, "exp": exp}
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, config.SECRET_KEY, algorithms=["HS256"])
        user = session.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized from None
    # Signing out everywhere bumps token_version, which retires every older token.
    if user is None or payload.get("v", 0) != (user.token_version or 0):
        raise unauthorized
    if user.suspended_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is suspended. Contact support.")
    return user
