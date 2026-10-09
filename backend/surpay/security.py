"""Protections applied to every request: security headers and sign-in rate limits."""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in _HEADERS.items():
            response.headers.setdefault(k, v)
        return response


class BodySizeLimit(BaseHTTPMiddleware):
    """Reject oversized requests before reading them (ID photos are the biggest: ~6 MB each)."""

    def __init__(self, app, max_bytes: int = 30 * 1024 * 1024):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        size = request.headers.get("content-length")
        if size and size.isdigit() and int(size) > self.max_bytes:
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "Upload too large"}, status_code=413)
        return await call_next(request)


# The most common leaked passwords (lower-cased); refused at sign-up and password change.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890", "qwertyuiop",
    "qwerty123", "11111111", "iloveyou", "abc12345", "letmein1", "welcome1", "sunshine1", "football1",
    "baseball1", "princess1", "admin123", "passw0rd", "p@ssw0rd", "monkey123", "dragon123", "000000000",
}


def check_password(password: str) -> None:
    if password.lower() in COMMON_PASSWORDS or len(set(password)) < 4:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "That password is too easy to guess. Please choose a stronger one.")


class RateLimiter:
    """At most `limit` failures per key in `window` seconds (per server process)."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str) -> deque:
        q, now = self._hits[key], time.monotonic()
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def check(self, *keys: str) -> None:
        if any(len(self._prune(k)) >= self.limit for k in keys):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Too many attempts. Please wait 15 minutes and try again.")

    def fail(self, *keys: str) -> None:
        for k in keys:
            self._prune(k).append(time.monotonic())

    def reset(self) -> None:
        self._hits.clear()


login_limiter = RateLimiter(limit=8, window=15 * 60)
