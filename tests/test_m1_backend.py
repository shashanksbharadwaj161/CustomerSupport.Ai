import asyncio
import json
import os
import sqlite3

import pytest

from tests.conftest import make_client

FAKE_KEY = "sk-ant-api03-" + "x" * 40 + "WXYZ"


def test_key_encrypted_at_rest_and_never_returned(data_dir):
    c, app = make_client()
    r = c.put("/api/settings/key", json={"key": FAKE_KEY})
    assert r.status_code == 200 and r.json()["key_last4"] == "WXYZ"
    s = c.get("/api/settings").json()
    assert s["key_present"] and s["key_last4"] == "WXYZ" and s["key_source"] == "settings"
    assert FAKE_KEY not in json.dumps(s)
    assert FAKE_KEY not in c.get("/api/health").text
    raw = sqlite3.connect(data_dir / "shaon.sqlite3").execute("SELECT value FROM settings WHERE key='anthropic_api_key'").fetchone()[0]
    assert FAKE_KEY not in raw and "WXYZ" not in raw  # ciphertext only
    assert app.state.app.secrets.file_mode() == 0o600
    assert app.state.app.provider().name == "anthropic"


def test_db_key_wins_over_env(data_dir, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-" + "e" * 30 + "ENVK")
    c, app = make_client()
    assert c.get("/api/settings").json()["key_source"] == "env"
    c.put("/api/settings/key", json={"key": FAKE_KEY})
    assert c.get("/api/settings").json()["key_last4"] == "WXYZ"


def test_key_edit_disabled_and_admin_password(data_dir, monkeypatch):
    c, _ = make_client(ALLOW_KEY_EDIT="false")
    assert c.put("/api/settings/key", json={"key": FAKE_KEY}).status_code == 403
    os.environ["ALLOW_KEY_EDIT"] = ""
    c, _ = make_client(ADMIN_PASSWORD="pw123", VISITOR_PASSCODE="visit-me")
    vis = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"passcode": "visit-me"}).json()["token"]}
    assert c.put("/api/settings/key", json={"key": FAKE_KEY}, headers=vis).status_code == 403  # visitors never touch the key
    adm = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"passcode": "pw123"}).json()["token"]}
    assert c.put("/api/settings/key", json={"key": FAKE_KEY}, headers=adm).status_code == 200  # admin-role token
    os.environ["ADMIN_PASSWORD"] = ""
    os.environ["VISITOR_PASSCODE"] = ""


def test_bad_key_rejected(data_dir):
    c, _ = make_client()
    assert c.put("/api/settings/key", json={"key": "hello"}).status_code == 400


def test_spend_cap_persists_across_restart(data_dir):
    c, app = make_client()
    assert c.put("/api/settings/spend-cap", json={"cap_usd": 3.5}).json()["cap_usd"] == 3.5
    app.state.app.spend.record("claude-haiku-5-5", {"input_tokens": 1000, "output_tokens": 1000}, "test")
    c2, app2 = make_client()
    s = c2.get("/api/settings").json()["spend"]
    assert s["cap_usd"] == 3.5 and s["spent_usd"] == pytest.approx(0.0006)


def test_spend_cap_blocks_calls(data_dir):
    from api.spend import SpendCapReached
    c, app = make_client()
    sp = app.state.app.spend
    sp.set_cap(0.0001)
    sp.record("claude-haiku-5-5", {"input_tokens": 10_000, "output_tokens": 0}, "test")
    with pytest.raises(SpendCapReached):
        sp.check()
    assert "spend cap reached" in " ".join(c.get("/api/health").json()["reasons"])


def test_demo_mode_without_key(data_dir):
    c, app = make_client()
    h = c.get("/api/health").json()
    assert h["mode"] == "demo" and h["provider"] == "demo"
    assert any("no Anthropic API key" in r for r in h["reasons"])


def test_log_scrubbing():
    from agent.logscrub import register_secret, scrub
    register_secret("sk-ant-custom-secret-value-1234")
    assert "sk-ant-api03" not in scrub("error with key sk-ant-api03-abcdefghijkl in it")
    assert "custom-secret" not in scrub("x sk-ant-custom-secret-value-1234 y")


def test_auth_tokens_and_rate_limit(data_dir):
    c, app = make_client(ADMIN_PASSWORD="pw")
    assert c.get("/api/profiles").status_code == 401
    assert c.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    tok = c.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    assert c.get("/api/profiles", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert not app.state.auth.token_ok(tok[:-2] + "xx")
    codes = [c.post("/api/auth/login", json={"password": "nope"}).status_code for _ in range(10)]
    assert 429 in codes
    os.environ["ADMIN_PASSWORD"] = ""


def test_ws_origin_check(data_dir):
    from api.auth import Auth
    a = Auth("", b"s", ["https://demo.example.com"])
    assert a.origin_ok("https://demo.example.com", "x.trycloudflare.com")
    assert a.origin_ok("https://x.trycloudflare.com", "x.trycloudflare.com")
    assert not a.origin_ok("https://evil.example", "x.trycloudflare.com")


def test_websocket_rejects_bad_origin(data_dir):
    from starlette.websockets import WebSocketDisconnect
    c, _ = make_client()
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/api/calls/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_text()
    assert e.value.code == 4403


def test_turn_engine_streams_sentences_with_script_language():
    from agent.brain import CallContext, TurnEngine
    from agent.llm.provider import FakeProvider
    from agent.presets import preset

    prov = FakeProvider(script=lambda m, s: "शाखा शनिवार को दस बजे खुलती है। क्या मैं और मदद करूँ?")
    ctx = CallContext(call_id="t", profile=preset("bank_support"))
    out = []

    async def emit(kind, data):
        out.append((kind, data))
    meta = asyncio.run(TurnEngine(ctx, prov, "claude-haiku-5-5").respond("शाखा कब खुलती है?", "hi", emit))
    sents = [d for k, d in out if k == "sentence"]
    assert len(sents) == 2 and all(d["lang"] == "hi" for d in sents)
    assert meta["reply_lang"] == "hi"
    sys_prompt = prov.calls[0]["system"]
    assert "NATIVE SCRIPT" in sys_prompt and "Never use digits" in sys_prompt
    assert "caller_language=hi" in prov.calls[0]["messages"][-1]["content"]
    assert len(ctx.history) == 2


def test_demo_provider_is_honest_in_language():
    from agent.llm.provider import DemoProvider
    r = asyncio.run(DemoProvider().stream(system="", messages=[{"role": "user", "content": "<context>\ncaller_language=ja\n</context>\nこんにちは"}]))
    assert "デモモード" in r.text


def test_raw_pcm_serializer():
    from pipecat.frames.frames import InputAudioRawFrame, InputTransportMessageFrame, OutputAudioRawFrame, OutputTransportMessageUrgentFrame
    from agent.pipeline.serializer import RawPCMSerializer
    s = RawPCMSerializer()
    f = asyncio.run(s.deserialize(b"\x01\x00" * 160))
    assert isinstance(f, InputAudioRawFrame) and f.sample_rate == 16000 and len(f.audio) == 320
    m = asyncio.run(s.deserialize('{"type":"ready"}'))
    assert isinstance(m, InputTransportMessageFrame) and m.message["type"] == "ready"
    assert asyncio.run(s.serialize(OutputAudioRawFrame(audio=b"\x00\x01", sample_rate=24000, num_channels=1))) == b"\x00\x01"
    assert json.loads(asyncio.run(s.serialize(OutputTransportMessageUrgentFrame(message={"a": 1}))))["a"] == 1


def test_split_sentences():
    from agent.brain import split_sentences
    s, rest = split_sentences("Hello there. How are you? I am")
    assert s == ["Hello there.", "How are you?"] and rest == "I am"
    s, rest = split_sentences("こんにちは。ご用件は")
    assert s == ["こんにちは。"]


def test_greeting_discloses_ai_in_every_language():
    from agent.presets import AI_DISCLOSURE, preset, normalize
    for kind in ("bank_support", "tourism", "ecommerce", "clinic_frontdesk", "custom"):
        g = preset(kind)["persona"]["greeting"]
        for lang, marker in AI_DISCLOSURE.items():
            assert marker.lower() in g[lang].lower(), (kind, lang)
    p = normalize({"persona": {"name": "X", "greeting": {"en": "Hi, how can I help?"}}})
    assert "AI assistant" in p["persona"]["greeting"]["en"]


def test_dotenv_last_value_wins(tmp_path, monkeypatch):
    """The .env made from .env.example has an empty ANTHROPIC_API_KEY= line; a value added below must win."""
    from api.config import _load_dotenv
    monkeypatch.delenv("SHAON_TEST_DOTENV", raising=False)
    f = tmp_path / ".env"
    f.write_text("﻿SHAON_TEST_DOTENV=\n# later\nSHAON_TEST_DOTENV=second\n", encoding="utf-8")
    _load_dotenv(f)
    import os
    assert os.environ["SHAON_TEST_DOTENV"] == "second"
    monkeypatch.delenv("SHAON_TEST_DOTENV")
