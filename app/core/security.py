"""Gateway protections: rate limiting and security headers.

Rate limits (sliding window of 60 seconds, kept in memory, so they are per API process):
- RATE_LIMIT_PER_MIN        default 100. One bucket per logged-in token, or per IP for anonymous callers.
- LOGIN_LIMIT_PER_MIN       default 10. Per IP, for login, registration and account activation, which are
                            the endpoints an attacker would hammer to guess passwords or tokens.
The client address is the direct peer address. X-Forwarded-For is deliberately not trusted: any caller can
forge it. Behind a reverse proxy, set the limits on the proxy as well.
"""
import hashlib
import os
import threading
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse

WINDOW_SECONDS = 60
AUTH_PATHS = ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/activate")
EXEMPT_PATHS = ("/api/v1/health",)


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def check(self, key: str, limit: int, now: float | None = None) -> int:
        """0 if the request is allowed (and counted), otherwise the seconds to wait before retrying."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(WINDOW_SECONDS - (now - hits[0])) + 1)
            hits.append(now)
            self._calls += 1
            if self._calls % 500 == 0:  # forget callers that went quiet, so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= WINDOW_SECONDS]:
                    del self._hits[k]
            return 0


limiter = RateLimiter()


def _limit(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _bucket(request: Request) -> tuple[str, int]:
    ip = request.client.host if request.client else "unknown"
    if request.url.path in AUTH_PATHS:
        return f"auth:{ip}", _limit("LOGIN_LIMIT_PER_MIN", 10)
    token = request.headers.get("authorization")
    key = "tok:" + hashlib.sha256(token.encode()).hexdigest()[:20] if token else f"ip:{ip}"
    return key, _limit("RATE_LIMIT_PER_MIN", 100)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Resource-Policy": "same-origin",
}


async def security_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/v1") and path not in EXEMPT_PATHS and request.method != "OPTIONS":
        key, limit = _bucket(request)
        wait = limiter.check(key, limit)
        if wait:
            return JSONResponse({"detail": "Too many requests"}, status_code=429,
                                headers={"Retry-After": str(wait), **SECURITY_HEADERS})
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if path.startswith("/api/v1"):
        # API answers hold case data: never let a browser or proxy keep them, and never run them as a page.
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
