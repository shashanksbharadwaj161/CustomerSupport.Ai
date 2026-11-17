"""Settings: API key, model selection, spend cap, local no-auth preview. All Anthropic calls are MOCKED (no network,
no paid calls): the real AnthropicProvider is used with its SDK client's stream/models replaced by fakes, so the test
sees exactly what would be sent to the API."""
import asyncio
import logging
import os

import pytest

from tests.conftest import make_client

FAKE_KEY = "sk-ant-api03-FAKE-test-key-0000000000000000wxyz"


class _Final:
    def __init__(self, model, text="Hello.", stop="end_turn"):
        class U:  # usage
            input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens = 100, 10, 0, 0

        class B:
            type = "text"

            def model_dump(self):
                return {"type": "text", "text": text}

        B.text = text
        self.model, self.usage, self.content, self.stop_reason = model, U(), [B()], stop


class FakeMessages:
    """Records every request; behaviour per model: {'model-id': 'notfound' | 'refusal' | 'ok'}."""

    def __init__(self, behaviour=None):
        self.sent, self.behaviour = [], behaviour or {}

    def stream(self, **kw):
        import anthropic
        import httpx2
        self.sent.append(kw)
        mode = self.behaviour.get(kw["model"], "ok")
        outer = self

        class CM:
            async def __aenter__(self):
                if mode == "notfound":
                    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
                    raise anthropic.NotFoundError("model not found", response=httpx2.Response(404, request=req), body=None)
                return self

            async def __aexit__(self, *a):
                return False

            @property
            def text_stream(self):
                async def gen():
                    if mode != "refusal":
                        yield "Hello."
                return gen()

            async def get_final_message(self):
                return _Final(kw["model"], "" if mode == "refusal" else "Hello.", "refusal" if mode == "refusal" else "end_turn")
        return CM()


def mock_provider(app, behaviour=None):
    """Replace the SDK client inside the REAL provider the app built (keeps model routing + spend code under test)."""
    st = app.state.app
    prov = st.provider()
    assert prov.name == "anthropic"
    fm = FakeMessages(behaviour)
    prov.client.messages = fm

    class Models:
        def list(self):
            async def gen():
                for mid, name in (("claude-haiku-5-5", "Claude Haiku 5.5"), ("claude-sonnet-5-5", "Claude Sonnet 5.5"),
                                  ("claude-future-9", "Claude Future 9")):
                    yield type("M", (), {"id": mid, "display_name": name, "max_input_tokens": 1000000, "max_tokens": 128000})()
            return gen()
    prov.client.models = Models()
    return prov, fm


def test_key_save_replace_remove_never_returned(data_dir, caplog):
    c, app = make_client()
    assert c.get("/api/settings").json()["key_present"] is False
    r = c.put("/api/settings/key", json={"key": FAKE_KEY})
    assert r.status_code == 200 and r.json()["key_last4"] == "wxyz"
    s = c.get("/api/settings")
    assert s.json()["key_present"] and s.json()["key_last4"] == "wxyz" and s.json()["provider"] == "anthropic"
    assert FAKE_KEY not in s.text
    # replace
    c.put("/api/settings/key", json={"key": FAKE_KEY.replace("wxyz", "abcd")})
    assert c.get("/api/settings").json()["key_last4"] == "abcd"
    # stored encrypted at rest
    row = app.state.app.db.one("SELECT value, encrypted FROM settings WHERE key='anthropic_api_key'")
    assert row["encrypted"] == 1 and "sk-ant" not in row["value"]
    # remove
    r = c.delete("/api/settings/key")
    assert r.status_code == 200 and r.json()["key_present"] is False
    assert c.get("/api/settings").json()["provider"] == "demo"
    assert c.put("/api/settings/key", json={"key": "not-a-key"}).status_code == 400
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("shaon").warning("debug %s", FAKE_KEY)
    assert FAKE_KEY not in caplog.text


def test_model_selection_persists_across_restart_and_is_what_is_sent(data_dir):
    c, app = make_client()
    c.put("/api/settings/key", json={"key": FAKE_KEY})
    b = c.get("/api/settings").json()
    assert b["model"] == "claude-haiku-5-5" and b["model_source"] == "default"
    assert {m["id"] for m in b["catalog"]} >= {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"}
    r = c.put("/api/settings/model", json={"model": "claude-sonnet-5-5", "fallback_model": "claude-haiku-5-5"})
    assert r.status_code == 200 and r.json()["model"] == "claude-sonnet-5-5" and r.json()["active_model"] == "claude-sonnet-5-5"
    # "restart": a brand-new app on the same data dir
    c2, app2 = make_client()
    b2 = c2.get("/api/settings").json()
    assert (b2["model"], b2["fallback_model"], b2["model_source"]) == ("claude-sonnet-5-5", "claude-haiku-5-5", "settings")
    prov, fm = mock_provider(app2)
    assert prov.default_model == "claude-sonnet-5-5" and prov.fallback_model == "claude-haiku-5-5"
    res = asyncio.run(prov.stream(system="s", messages=[{"role": "user", "content": "hi"}]))
    sent = fm.sent[-1]
    assert sent["model"] == "claude-sonnet-5-5" and res.model == "claude-sonnet-5-5"
    assert sent["thinking"] == {"type": "between_tools"} and sent["output_config"] == {"effort": "low"}  # Sonnet 5.5 rules
    # calls use the saved model (Hooks gets it at call start)
    assert app2.state.app.llm_model() == "claude-sonnet-5-5"


@pytest.mark.parametrize("model,thinking,has_effort", [
    ("claude-haiku-5-5", {"type": "disabled"}, True),
    ("claude-opus-5-5", None, True),          # thinking cannot be disabled -> omitted
    ("claude-sonnet-5-5", {"type": "between_tools"}, True),
    ("claude-opus-5", {"type": "disabled"}, True),
    ("claude-haiku-4-5", None, False),         # effort errors on Haiku 4.5
])
def test_per_model_request_params(model, thinking, has_effort):
    from agent.llm.models import request_params
    p = request_params(model)
    assert p.get("thinking") == thinking
    assert ("output_config" in p) == has_effort


def test_switching_model_invalidates_cached_provider(data_dir):
    c, app = make_client()
    c.put("/api/settings/key", json={"key": FAKE_KEY})
    p1 = app.state.app.provider()
    c.put("/api/settings/model", json={"model": "claude-opus-5-5", "fallback_model": ""})
    p2 = app.state.app.provider()
    assert p1 is not p2 and p2.default_model == "claude-opus-5-5" and p2.fallback_model is None


def test_unlisted_model_needs_explicit_opt_in_and_is_marked_unverified(data_dir):
    c, app = make_client()
    c.put("/api/settings/key", json={"key": FAKE_KEY})
    r = c.put("/api/settings/model", json={"model": "claude-made-up-1"})
    assert r.status_code == 400 and "not in the model list" in r.json()["detail"]
    assert c.put("/api/settings/model", json={"model": "Bad ID!"}).status_code == 400
    r = c.put("/api/settings/model", json={"model": "claude-made-up-1", "allow_unlisted": True})
    assert r.status_code == 200 and r.json()["model"] == "claude-made-up-1" and r.json()["model_known"] is False


def test_refresh_models_uses_live_list_and_unlisted_live_model_becomes_known(data_dir):
    c, app = make_client()
    c.put("/api/settings/key", json={"key": FAKE_KEY})
    mock_provider(app)
    r = c.post("/api/settings/models/refresh")
    assert r.status_code == 200 and r.json()["live_count"] == 3
    fut = [m for m in r.json()["catalog"] if m["id"] == "claude-future-9"][0]
    assert fut["live"] and fut["in"] is None  # price unknown -> conservative rate used for the cap
    assert c.put("/api/settings/model", json={"model": "claude-future-9"}).status_code == 200


def test_refresh_without_key_is_an_honest_error(data_dir):
    c, _ = make_client()
    r = c.post("/api/settings/models/refresh")
    assert r.status_code == 400 and "Add an API key" in r.json()["detail"]


def test_fallback_model_answers_when_main_model_not_found(data_dir):
    c, app = make_client()
    c.put("/api/settings/key", json={"key": FAKE_KEY})
    c.put("/api/settings/model", json={"model": "claude-opus-5-5", "fallback_model": "claude-haiku-5-5"})
    prov, fm = mock_provider(app, {"claude-opus-5-5": "notfound"})
    res = asyncio.run(prov.stream(system="s", messages=[{"role": "user", "content": "hi"}]))
    assert [s["model"] for s in fm.sent] == ["claude-opus-5-5", "claude-haiku-5-5"]
    assert res.model == "claude-haiku-5-5" and res.fallback_from.startswith("claude-opus-5-5")
    spend = app.state.app.db.all("SELECT model, usd FROM spend")
    assert spend[-1]["model"] == "claude-haiku-5-5" and spend[-1]["usd"] > 0


def test_test_key_reports_model_and_friendly_404(data_dir):
    c, app = make_client()
    c.put("/api/settings/key", json={"key": FAKE_KEY})
    c.put("/api/settings/model", json={"model": "claude-sonnet-5-5", "fallback_model": ""})
    prov, fm = mock_provider(app)
    r = c.post("/api/settings/key/test")
    assert r.status_code == 200 and r.json()["model"] == "claude-sonnet-5-5" and len(fm.sent) == 1
    prov.client.messages = FakeMessages({"claude-sonnet-5-5": "notfound"})
    r = c.post("/api/settings/key/test")
    assert r.status_code == 400 and "not found for this key" in r.json()["error"] and FAKE_KEY not in r.text


def test_unknown_model_is_never_free_for_the_cap():
    from agent.llm.pricing import cost_usd
    u = {"input_tokens": 1_000_000, "output_tokens": 0}
    assert cost_usd("claude-made-up-1", u) >= cost_usd("claude-opus-5-5", u) > 0


def test_spend_cap_edit_and_history_kept(data_dir):
    c, app = make_client()
    st = app.state.app
    st.spend.record("claude-haiku-5-5", {"input_tokens": 1000, "output_tokens": 100}, "reply")
    spent = c.get("/api/settings").json()["spend"]["spent_usd"]
    assert spent > 0
    r = c.put("/api/settings/spend-cap", json={"cap_usd": 25})
    assert r.status_code == 200 and r.json()["cap_usd"] == 25 and r.json()["cap_source"] == "user"
    assert c.put("/api/settings/spend-cap", json={"cap_usd": -1}).status_code == 400
    assert c.put("/api/settings/spend-cap", json={"cap_usd": "abc"}).status_code == 400
    assert c.get("/api/settings").json()["spend"]["spent_usd"] == spent


def test_local_preview_resets_a_stale_zero_cap_but_never_a_user_cap(data_dir):
    os.environ["SHAON_LOCAL_PREVIEW"] = "1"
    try:
        c, app = make_client()
        st = app.state.app
        st.spend.record("claude-haiku-5-5", {"input_tokens": 10, "output_tokens": 1}, "reply")
        # a launcher wrote 0 directly (legacy row, no 'user' marker)
        st.db.execute("INSERT OR REPLACE INTO settings(key,value,encrypted,updated_at) VALUES('spend_cap_usd','0',0,'x')")
        st.db.execute("DELETE FROM settings WHERE key='spend_cap_source'")
        c2, app2 = make_client()
        s = c2.get("/api/settings").json()["spend"]
        assert s["cap_usd"] == 10 and s["notice"] and s["spent_usd"] > 0 and not s["blocked"]
        # the user deliberately chooses 0: kept across restarts
        c2.put("/api/settings/spend-cap", json={"cap_usd": 0})
        c3, _ = make_client()
        s3 = c3.get("/api/settings").json()["spend"]
        assert s3["cap_usd"] == 0 and s3["cap_source"] == "user" and s3["notice"] is None
    finally:
        os.environ["SHAON_LOCAL_PREVIEW"] = ""


def test_local_preview_has_no_gate_even_with_stale_passcodes(data_dir):
    os.environ.update(SHAON_LOCAL_PREVIEW="1", ADMIN_PASSWORD="stale-admin-pass-123", VISITOR_PASSCODE="stale-visitor",
                      ALLOW_KEY_EDIT="false", SPEND_CAP_USD="0")
    try:
        c, app = make_client()
        a = c.get("/api/auth/status").json()
        assert a["required"] is False and a["local_preview"] is True
        for path in ("/api/settings", "/api/profiles", "/api/calls", "/api/knowledge", "/api/engines"):
            assert c.get(path).status_code == 200, path
        s = c.get("/api/settings").json()
        assert s["key_edit_allowed"] is True and s["spend"]["cap_usd"] == 10
        assert c.put("/api/settings/key", json={"key": FAKE_KEY}).status_code == 200
        assert c.put("/api/settings/model", json={"model": "claude-sonnet-5-5"}).status_code == 200
        # never through a proxy / tunnel: forwarded requests are refused outright (no unauthenticated key endpoint in public)
        for h in ({"cf-connecting-ip": "203.0.113.5"}, {"x-forwarded-for": "203.0.113.5"}):
            assert c.get("/api/settings", headers=h).status_code == 403
            assert c.put("/api/settings/key", json={"key": FAKE_KEY}, headers=h).status_code == 403
    finally:
        for k in ("SHAON_LOCAL_PREVIEW", "ADMIN_PASSWORD", "VISITOR_PASSCODE", "ALLOW_KEY_EDIT", "SPEND_CAP_USD"):
            os.environ[k] = ""


def test_local_preview_and_exposed_cannot_combine(data_dir):
    os.environ.update(SHAON_LOCAL_PREVIEW="1", SHAON_EXPOSED="1")
    try:
        with pytest.raises(RuntimeError, match="cannot both be on"):
            make_client()
    finally:
        os.environ["SHAON_LOCAL_PREVIEW"] = os.environ["SHAON_EXPOSED"] = ""


def test_share_mode_still_gates_settings(data_dir):
    os.environ.update(SHAON_EXPOSED="1", ADMIN_PASSWORD="admin-pass-12345", VISITOR_PASSCODE="visit-pass")
    try:
        c, app = make_client()
        assert c.get("/api/settings").status_code == 401
        assert c.put("/api/settings/model", json={"model": "claude-sonnet-5-5"}).status_code == 401
    finally:
        for k in ("SHAON_EXPOSED", "ADMIN_PASSWORD", "VISITOR_PASSCODE"):
            os.environ[k] = ""
