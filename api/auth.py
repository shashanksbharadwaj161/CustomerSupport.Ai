"""Auth + rate limiting (CLAUDE.md M2 rule; DEPLOY.md security rules).

- No ADMIN_PASSWORD: local mode, no login (loopback edits only; see state.require_admin).
- ADMIN_PASSWORD set: POST /api/auth/login issues a short-lived HMAC-signed token; every /api call
  and the WebSocket upgrade need it (header `Authorization: Bearer`, cookie `shaon_token`, or `?token=`).
- WebSocket Origin is checked against ALLOWED_ORIGINS + the request's own host (CORS does not cover WS).
- Token-bucket rate limits per client IP for login, call start and crawl.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request

LIMITS = {"login": (5, 60), "call_start": (12, 60), "crawl": (6, 60), "voice_preview": (30, 60), "ask": (20, 60)}
PUBLIC = {"/api/health", "/api/auth/login", "/api/auth/status"}
TOKEN_TTL = 12 * 3600


class Auth:
    def __init__(self, password: str, secret: bytes, allowed_origins: list[str]):
        self.password = password
        self.secret = hashlib.sha256(b"shaon-auth" + secret).digest()
        self.allowed_origins = [o.rstrip("/") for o in allowed_origins]
        self._buckets: dict[tuple[str, str], list[float]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.password)

    # tokens
    def issue(self) -> str:
        body = json.dumps({"exp": int(time.time()) + TOKEN_TTL}).encode()
        sig = hmac.new(self.secret, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + base64.urlsafe_b64encode(sig).decode().rstrip("=")

    def token_ok(self, token: str | None) -> bool:
        if not self.enabled:
            return True
        if not token or "." not in token:
            return False
        try:
            b64, s64 = token.split(".", 1)
            body = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
            sig = base64.urlsafe_b64decode(s64 + "=" * (-len(s64) % 4))
        except Exception:
            return False
        if not hmac.compare_digest(sig, hmac.new(self.secret, body, hashlib.sha256).digest()):
            return False
        try:
            return json.loads(body)["exp"] > time.time()
        except Exception:
            return False

    def login(self, password: str) -> str:
        if not self.enabled:
            return ""
        if not hmac.compare_digest(password.encode(), self.password.encode()):
            raise HTTPException(401, "Wrong password.")
        return self.issue()

    @staticmethod
    def token_from(request: Request) -> str | None:
        h = request.headers.get("authorization", "")
        if h.lower().startswith("bearer "):
            return h[7:].strip()
        return request.cookies.get("shaon_token") or request.query_params.get("token")

    def check_request(self, request: Request) -> None:
        if self.enabled and not self.token_ok(self.token_from(request)):
            raise HTTPException(401, "Login required.")

    def origin_ok(self, origin: str | None, host: str | None) -> bool:
        if not origin:
            return True  # non-browser clients (no Origin header) still need the token when auth is on
        o = origin.rstrip("/")
        if o in self.allowed_origins:
            return True
        netloc = urlparse(o).netloc
        return bool(host) and netloc == host

    # rate limiting
    def rate_limit_key(self, client: str, bucket: str) -> bool:
        n, per = LIMITS[bucket]
        t = time.time()
        with self._lock:
            q = [x for x in self._buckets.get((client, bucket), []) if t - x < per]
            ok = len(q) < n
            if ok:
                q.append(t)
            self._buckets[(client, bucket)] = q
        return ok

    def rate_limit(self, request: Request, bucket: str) -> None:
        client = request.client.host if request.client else "?"
        if not self.rate_limit_key(client, bucket):
            raise HTTPException(429, f"Too many requests ({bucket}). Try again in a minute.")
