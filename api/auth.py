"""Auth, roles, origin/host checks and rate limiting (CLAUDE.md M2 rule; DEPLOY.md security rules).

Modes
- Local (no ADMIN_PASSWORD, no VISITOR_PASSCODE): no login; secret edits only from this machine (state.require_admin).
- ADMIN_PASSWORD only: every /api route needs an admin token (POST /api/auth/login).
- Share mode (scripts/share.ps1 sets VISITOR_PASSCODE + ADMIN_PASSWORD, random per launch): a visitor token may
  only start calls, read the agent list / voices / readiness; everything else (Settings, Studio, key, knowledge,
  logs) needs the admin passcode.
Tokens are short-lived HMAC-signed {exp, role}; sent as `Authorization: Bearer`, httpOnly cookie, or `?token=` (WS).
Exposed mode also checks Host and Origin against localhost + the tunnel host learned at launch (CORS does not cover
WebSockets) and rate-limits per real client IP (CF-Connecting-IP, trusted only from the local tunnel process).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import pathlib
import re
import threading
import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request

LIMITS = {"login": (8, 60), "call_start": (12, 60), "crawl": (6, 60), "voice_preview": (30, 60), "ask": (20, 60), "api": (240, 60)}
PUBLIC = {"/api/health", "/health", "/api/auth/login", "/api/auth/status", "/api/auth/logout"}
TOKEN_TTL = 12 * 3600

# routes a VISITOR may use (everything else under /api needs ADMIN when roles are on)
VISITOR_ROUTES = [
    ("GET", re.compile(r"^/api/profiles$")),
    ("GET", re.compile(r"^/api/voices$")),
    ("GET", re.compile(r"^/api/voices/personas$")),
    ("GET", re.compile(r"^/api/ready$")),
    ("POST", re.compile(r"^/api/calls/offer$")),
    ("PATCH", re.compile(r"^/api/calls/offer$")),
    ("WS", re.compile(r"^/api/calls/ws$")),
    ("WS", re.compile(r"^/api/ws-check$")),
]
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def required_role(method: str, path: str) -> str:
    if path in PUBLIC or not path.startswith("/api/") or path.startswith("/api/docs") or path == "/api/openapi.json":
        return "public"
    if path == "/api/share/status":
        return "local"  # launcher only (checked in the route)
    for m, rx in VISITOR_ROUTES:
        if m == method and rx.match(path):
            return "visitor"
    return "admin"


def has_forwarding_headers(headers) -> bool:
    return any(h in headers for h in ("cf-connecting-ip", "x-forwarded-for", "cf-ray", "x-real-ip"))


def client_ip(request) -> str:
    """Real client IP. Behind the Quick Tunnel every peer is 127.0.0.1 (cloudflared), so CF-Connecting-IP is used,
    but only when the TCP peer is loopback (i.e. the header came through the local tunnel process)."""
    peer = request.client.host if request.client else "?"
    try:
        loop = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        loop = peer in ("localhost", "testclient")
    if loop:
        fwd = request.headers.get("cf-connecting-ip") or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if fwd:
            return fwd
    return peer


class Auth:
    def __init__(self, password: str, secret: bytes, allowed_origins: list[str], visitor_passcode: str = "",
                 exposed: bool = False, share_host_file: pathlib.Path | None = None):
        self.password = password
        self.visitor = visitor_passcode
        self.secret = hashlib.sha256(b"shaon-auth" + secret).digest()
        self.allowed_origins = [o.rstrip("/") for o in allowed_origins]
        self.exposed = exposed
        self.share_host_file = share_host_file
        self._host_cache: tuple[float, str | None] = (-1.0, None)
        self._buckets: dict[tuple[str, str], list[float]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.password or self.visitor)

    @property
    def roles_on(self) -> bool:
        return bool(self.visitor)

    # ---- tokens
    def issue(self, role: str = "admin") -> str:
        body = json.dumps({"exp": int(time.time()) + TOKEN_TTL, "role": role}).encode()
        sig = hmac.new(self.secret, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + base64.urlsafe_b64encode(sig).decode().rstrip("=")

    def role_of_token(self, token: str | None) -> str | None:
        if not token or "." not in token:
            return None
        try:
            b64, s64 = token.split(".", 1)
            body = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
            sig = base64.urlsafe_b64decode(s64 + "=" * (-len(s64) % 4))
        except Exception:
            return None
        if not hmac.compare_digest(sig, hmac.new(self.secret, body, hashlib.sha256).digest()):
            return None
        try:
            d = json.loads(body)
            return d.get("role", "admin") if d["exp"] > time.time() else None
        except Exception:
            return None

    def token_ok(self, token: str | None, need: str = "visitor") -> bool:
        if not self.enabled or need == "public":
            return True
        role = self.role_of_token(token)
        if role is None:
            return False
        if need == "admin" or not self.roles_on:
            return role == "admin"
        return role in ("visitor", "admin")

    def login(self, passcode: str) -> tuple[str, str]:
        """Returns (token, role). Admin passcode wins if both match."""
        if not self.enabled:
            return "", "admin"
        pc = passcode.encode()
        if self.password and hmac.compare_digest(pc, self.password.encode()):
            return self.issue("admin"), "admin"
        if self.visitor and hmac.compare_digest(pc, self.visitor.encode()):
            return self.issue("visitor"), "visitor"
        raise HTTPException(401, "Wrong passcode.")

    @staticmethod
    def token_from(request) -> str | None:
        h = request.headers.get("authorization", "")
        if h.lower().startswith("bearer "):
            return h[7:].strip()
        return request.cookies.get("shaon_token") or request.query_params.get("token")

    def role_from(self, request) -> str | None:
        if not self.enabled:
            return "admin"
        return self.role_of_token(self.token_from(request))

    def check_request(self, request: Request, need: str = "visitor") -> None:
        if self.enabled and not self.token_ok(self.token_from(request), need):
            raise HTTPException(401 if self.role_from(request) is None else 403,
                                "Login required." if self.role_from(request) is None else "Admin passcode required.")

    # ---- host / origin (exposed mode)
    def share_host(self) -> str | None:
        f = self.share_host_file
        if not f:
            return None
        try:
            m = f.stat().st_mtime
        except OSError:
            return None
        if m != self._host_cache[0]:
            try:
                h = f.read_text(encoding="utf-8").strip().lower() or None
            except OSError:
                h = None
            self._host_cache = (m, h)
        return self._host_cache[1]

    def host_ok(self, host_header: str | None) -> bool:
        if not self.exposed:
            return True
        host = (host_header or "").lower()
        name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        if name in LOCAL_HOSTS or name == "testserver":
            return True
        sh = self.share_host()
        return bool(sh) and host == sh

    def origin_ok(self, origin: str | None, host: str | None) -> bool:
        if not origin:
            return True  # non-browser clients (no Origin header) still need the token when auth is on
        o = origin.rstrip("/").lower()
        if o in [a.lower() for a in self.allowed_origins]:
            return True
        u = urlparse(o)
        if self.exposed:
            name = (u.hostname or "")
            if name in ("localhost", "127.0.0.1", "::1"):
                return True
            sh = self.share_host()
            return bool(sh) and u.scheme == "https" and u.netloc == sh
        return bool(host) and u.netloc == host

    # ---- rate limiting (per real client IP)
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
        if not self.rate_limit_key(client_ip(request), bucket):
            raise HTTPException(429, f"Too many requests ({bucket}). Try again in a minute.")
