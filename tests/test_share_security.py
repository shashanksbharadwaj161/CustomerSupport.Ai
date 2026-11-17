"""Share mode (public Quick Tunnel link) security, exercised through the PUBLIC path: tunnel Host header,
CF-Connecting-IP from cloudflared, browser Origin. Fast, no models."""
import asyncio
import os

import httpx
import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import make_client

PUB = "abc-def-ghi.trycloudflare.com"
ORIGIN = f"https://{PUB}"
ADMIN, VISITOR = "admin-pass-1234567", "visit-4321"


@pytest.fixture
def share(data_dir, monkeypatch):
    host_file = data_dir.parent / "share_host.txt"
    data_dir.mkdir(parents=True, exist_ok=True)
    host_file.write_text(PUB)
    env = {"SHAON_EXPOSED": "1", "ADMIN_PASSWORD": ADMIN, "VISITOR_PASSCODE": VISITOR, "ALLOW_KEY_EDIT": "false",
           "SHAON_MAX_CALLS": "1", "SHAON_SHARE_HOST_FILE": str(host_file), "SHAON_SEED_DEMO": "0",
           "CRAWL_ALLOWLIST": "example.org,169.254.169.254,10.0.0.1,0.0.0.0,2130706433,::1,public.example"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    c, app = make_client()
    c.headers.update({"host": PUB, "cf-connecting-ip": "203.0.113.7", "origin": ORIGIN})
    yield c, app
    for k in env:
        os.environ[k] = ""


def login(c, pc, ip="203.0.113.7"):
    r = c.post("/api/auth/login", json={"passcode": pc}, headers={"cf-connecting-ip": ip})
    return r


def bearer(c, pc):
    return {"Authorization": "Bearer " + login(c, pc).json()["token"]}


def test_public_health_and_missing_or_wrong_passcode(share):
    c, _ = share
    assert c.get("/health").json()["ok"] is True
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/profiles").status_code == 401           # missing passcode
    assert login(c, "wrong").status_code == 401                  # wrong passcode
    assert login(c, VISITOR).json()["role"] == "visitor"
    assert login(c, ADMIN).json()["role"] == "admin"


def test_visitor_can_call_but_not_administer(share):
    c, _ = share
    v = bearer(c, VISITOR)
    for path in ("/api/profiles", "/api/voices", "/api/ready"):
        assert c.get(path, headers=v).status_code == 200, path
    for method, path in [("get", "/api/settings"), ("get", "/api/engines"), ("get", "/api/calls"), ("get", "/api/profiles/lotus-bank"),
                         ("get", "/api/profiles/lotus-bank/prompt"), ("put", "/api/profiles/lotus-bank"), ("post", "/api/profiles"),
                         ("post", "/api/knowledge"), ("get", "/api/knowledge"), ("put", "/api/settings/key"), ("post", "/api/voices/preview"),
                         ("put", "/api/settings/spend-cap")]:
        r = getattr(c, method)(path, headers=v, **({"json": {}} if method in ("post", "put") else {}))
        assert r.status_code == 403, (method, path, r.status_code)
    a = bearer(c, ADMIN)
    s = c.get("/api/settings", headers=a).json()
    assert "spend" in s and s["key_edit_allowed"] is False      # admin sees spend + cap; key locked while shared
    assert c.put("/api/settings/key", json={"key": "sk-ant-" + "x" * 30}, headers=a).status_code == 403


def test_host_and_origin_checks(share):
    c, _ = share
    v = bearer(c, VISITOR)
    assert c.get("/api/ready", headers={**v, "host": "evil.example"}).status_code == 421       # unknown Host
    assert c.post("/api/auth/login", json={"passcode": VISITOR}, headers={"origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/auth/login", json={"passcode": VISITOR}, headers={"origin": "https://other.trycloudflare.com"}).status_code == 403
    assert c.post("/api/auth/login", json={"passcode": VISITOR}, headers={"origin": "http://localhost:8000"}).status_code == 200
    tok = login(c, VISITOR).json()["token"]
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect(f"/api/ws-check?token={tok}", headers={"origin": "https://evil.example", "host": PUB}) as ws:
            ws.receive_text()
    assert e.value.code == 4403
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/api/ws-check", headers={"origin": ORIGIN, "host": PUB}) as ws:  # no passcode
            ws.receive_text()
    assert e.value.code == 4401
    with c.websocket_connect(f"/api/ws-check?token={tok}", headers={"origin": ORIGIN, "host": PUB}) as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "ping"


def test_busy_when_max_concurrent_calls_reached(share):
    c, app = share
    v = bearer(c, VISITOR)
    app.state.app.active_calls["call_x"] = {"transport": "websocket"}   # one call already running, max 1
    assert c.get("/api/ready", headers=v).json()["busy"] is True
    r = c.post("/api/calls/offer", json={"sdp": "v=0", "type": "offer"}, headers=v)
    assert r.status_code == 503 and r.json()["busy"] is True
    tok = v["Authorization"].split()[1]
    with c.websocket_connect(f"/api/calls/ws?token={tok}", headers={"origin": ORIGIN, "host": PUB}) as ws:
        assert '"busy"' in ws.receive_text()
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
    assert e.value.code == 4503


def test_max_call_length_timer_notifies_then_ends():
    from agent.pipeline.run import call_timer
    events = []

    class FakeTask:
        async def cancel(self):
            events.append("cancel")

    async def notify():
        events.append("notify")
    asyncio.run(call_timer(FakeTask(), 0.05, notify))
    assert events == ["notify", "cancel"]


def test_rate_limit_is_per_real_client_ip(share):
    c, _ = share
    codes = [login(c, "nope", ip="198.51.100.1").status_code for _ in range(9)]
    assert codes[-1] == 429
    assert login(c, VISITOR, ip="198.51.100.2").status_code == 200   # another visitor is not punished


def test_tunnel_requests_are_never_treated_as_local(data_dir, monkeypatch):
    c, _ = make_client()  # local mode: no passwords, edits allowed only from this machine
    r = c.put("/api/settings/key", json={"key": "sk-ant-" + "y" * 30}, headers={"cf-connecting-ip": "203.0.113.9"})
    assert r.status_code == 403
    assert c.get("/api/share/status").status_code == 200
    assert c.get("/api/share/status", headers={"cf-connecting-ip": "203.0.113.9"}).status_code == 404


SSRF_URLS = [
    "http://127.0.0.1:22/", "http://localhost:8000/api/settings", "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/", "http://10.0.0.1/", "http://0.0.0.0/", "http://2130706433/", "http://user:pw@example.org/",
    "file:///etc/passwd", "http://127.0.0.1:8000/demo-sites/../api/settings",
]


@pytest.mark.parametrize("url", SSRF_URLS)
def test_ssrf_attempts_through_the_public_url_are_refused(share, url):
    c, _ = share
    a = bearer(c, ADMIN)
    r = c.post("/api/knowledge", json={"url": url, "permission_confirmed": True}, headers=a)
    assert r.status_code == 400, (url, r.status_code, r.text)


def test_visitor_cannot_ingest_at_all(share):
    c, _ = share
    assert c.post("/api/knowledge", json={"url": "https://example.org/", "permission_confirmed": True},
                  headers=bearer(c, VISITOR)).status_code == 403


def test_redirect_hop_to_internal_address_is_refused(monkeypatch):
    """public.example looks public but redirects to 127.0.0.1: every hop is re-checked."""
    import socket as S

    from agent.knowledge import netguard
    from agent.knowledge.crawler import Limits, crawl
    real = S.getaddrinfo

    def fake(host, *a, **k):
        if host == "public.example":
            return [(S.AF_INET, S.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]
        return real(host, *a, **k)
    monkeypatch.setattr(netguard.socket, "getaddrinfo", fake)

    def handler(req: httpx.Request):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/api/settings"})
    events = []

    async def emit(k, d):
        events.append((k, d))
    pages = asyncio.run(crawl("http://public.example/", Limits(delay_s=0, render_js="never"), emit,
                              guard=netguard.make_guard(), transport=httpx.MockTransport(handler)))
    assert pages == []
    assert any(k == "skipped" and "private/local" in d["reason"] for k, d in events)


def test_logs_never_contain_passcodes_or_tokens():
    from agent.logscrub import register_secret, scrub
    register_secret(VISITOR)
    out = scrub(f"GET /api/calls/ws?token=abc.def-123 passcode {VISITOR}")
    assert VISITOR not in out and "abc.def-123" not in out
