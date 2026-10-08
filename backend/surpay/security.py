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
