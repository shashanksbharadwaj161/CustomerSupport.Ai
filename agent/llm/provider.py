"""Pluggable LLM providers.

- AnthropicProvider: Claude Haiku 5.5 (per-language Sonnet 5.5 fallback chosen by the caller),
  streaming, prompt caching of the system prompt (+ site brief), spend recorded + capped.
- FakeProvider: deterministic, no network. Used by tests and the E2E check (SHAON_LLM_PROVIDER=fake);
  the UI banner says "fake LLM" whenever it is active.
- DemoProvider: used when no API key is configured. Says honestly (in the caller's language)
  that no language model is configured. Never pretends to answer.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from agent.logscrub import register_secret


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResult:
    text: str
    model: str
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)
    content: list = field(default_factory=list)  # raw assistant content blocks (for tool loops)
    ttft_ms: int | None = None
    total_ms: int | None = None
    refused: bool = False
    fallback_from: str | None = None  # "<model>: <reason>" when the fallback model answered instead


OnText = Callable[[str], Awaitable[None]]


class LLMProvider(ABC):
    name = "base"
    is_real = False  # True only when replies come from a real model

    @abstractmethod
    async def stream(self, *, system: str, messages: list[dict], model: str | None = None,
                     max_tokens: int = 300, tools: list[dict] | None = None,
                     on_text: OnText | None = None, purpose: str = "reply", call_id: str | None = None) -> LLMResult: ...

    async def complete_json(self, *, system: str, prompt: str, model: str | None = None,
                            max_tokens: int = 400, purpose: str = "json", call_id: str | None = None) -> dict:
        """Return a JSON object. Raises ValueError if the model output is not valid JSON."""
        r = await self.stream(system=system, messages=[{"role": "user", "content": prompt}], model=model,
                              max_tokens=max_tokens, purpose=purpose, call_id=call_id)
        return parse_json_object(r.text)


def parse_json_object(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in model output")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("JSON is not an object")
    return obj


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    is_real = True

    def __init__(self, api_key: str, default_model: str, spend=None, effort: str = "low", fallback_model: str | None = None):
        import anthropic

        register_secret(api_key)
        self._anthropic = anthropic
        self.client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=2, timeout=30)
        self.default_model = default_model
        self.fallback_model = fallback_model
        self.spend = spend
        self.effort = effort

    def _request(self, *, model, system, messages, max_tokens, tools) -> dict:
        from agent.llm.models import request_params
        kw: dict[str, Any] = dict(
            model=model, max_tokens=max_tokens, messages=messages,
            # cached prefix: rules + persona + guardrails + site brief (byte-stable per profile version)
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            **request_params(model, self.effort),  # per-model: a param one model needs is a 400 on another
        )
        if tools:
            kw["tools"] = tools
        return kw

    async def stream(self, *, system, messages, model=None, max_tokens=300, tools=None, on_text=None,
                     purpose="reply", call_id=None) -> LLMResult:
        model = model or self.default_model
        if self.spend:
            self.spend.check()  # raises SpendCapReached
        emitted = False

        async def relay(chunk):
            nonlocal emitted
            emitted = True
            if on_text:
                await on_text(chunk)

        try:
            res = await self._once(model, system, messages, max_tokens, tools, relay, purpose, call_id)
        except (self._anthropic.NotFoundError, self._anthropic.InternalServerError) as e:
            # model unavailable for this key (404) or overloaded (529/5xx): try the fallback model once, if nothing was spoken yet
            fb = self.fallback_model
            if not fb or fb == model or emitted:
                raise
            res = await self._once(fb, system, messages, max_tokens, tools, relay, purpose, call_id)
            res.fallback_from = f"{model}: {type(e).__name__}"
            return res
        if res.refused and not emitted and self.fallback_model and self.fallback_model != model:
            res2 = await self._once(self.fallback_model, system, messages, max_tokens, tools, relay, purpose, call_id)
            res2.fallback_from = f"{model}: refusal"
            return res2
        return res

    async def _once(self, model, system, messages, max_tokens, tools, on_text, purpose, call_id) -> LLMResult:
        kw = self._request(model=model, system=system, messages=messages, max_tokens=max_tokens, tools=tools)
        t0 = time.perf_counter()
        ttft = None
        async with self.client.messages.stream(**kw) as s:
            async for chunk in s.text_stream:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                await on_text(chunk)
            msg = await s.get_final_message()
        usage = {k: getattr(msg.usage, k, 0) or 0 for k in
                 ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
        served = getattr(msg, "model", None) or model  # the model the API says answered
        if self.spend:
            self.spend.record(served if isinstance(served, str) else model, usage, purpose, call_id)
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in msg.content if b.type == "tool_use"]
        return LLMResult(text=text, model=served if isinstance(served, str) else model, stop_reason=msg.stop_reason,
                         usage=usage, tool_calls=calls,
                         content=[b.model_dump() for b in msg.content if b.type in ("text", "tool_use")],
                         ttft_ms=round(ttft * 1000) if ttft else None,
                         total_ms=round((time.perf_counter() - t0) * 1000), refused=msg.stop_reason == "refusal")

    async def list_models(self) -> list[dict]:
        """Models this key can use (Models API, free). Used only when the user presses Refresh in Settings."""
        out = []
        async for m in self.client.models.list():
            out.append({"id": m.id, "display_name": getattr(m, "display_name", None),
                        "max_input_tokens": getattr(m, "max_input_tokens", None), "max_tokens": getattr(m, "max_tokens", None)})
        return out

    async def test_key(self) -> dict:
        """One tiny call to verify the key (Settings 'Test key')."""
        if self.spend:
            self.spend.check()  # the cap applies to every Claude call, the key test too
        r = await self._once(self.default_model, "Reply with the single word OK.", [{"role": "user", "content": "ping"}],
                             16, None, _noop, "key_test", None)
        return {"ok": True, "model": r.model, "requested_model": self.default_model, "reply": r.text[:20]}


# --- no-network providers -------------------------------------------------------------------

_DEMO_MSG = {
    "en": "Demo mode: no language model key is configured yet, so I can hear you but cannot answer. Please add a key in Settings.",
    "ja": "デモモードです。言語モデルのキーが未設定のため、お答えできません。設定画面でキーを追加してください。",
    "hi": "यह डेमो मोड है। भाषा मॉडल की कुंजी अभी सेट नहीं है, इसलिए मैं जवाब नहीं दे सकती। कृपया सेटिंग्स में कुंजी जोड़ें।",
    "bn": "এটি ডেমো মোড। ভাষা মডেলের কী এখনও সেট করা নেই, তাই আমি উত্তর দিতে পারছি না। দয়া করে সেটিংসে কী যোগ করুন।",
    "kn": "ಇದು ಡೆಮೊ ಮೋಡ್. ಭಾಷಾ ಮಾದರಿಯ ಕೀ ಇನ್ನೂ ಹೊಂದಿಸಿಲ್ಲ, ಆದ್ದರಿಂದ ನಾನು ಉತ್ತರಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಸೆಟ್ಟಿಂಗ್ಸ್‌ನಲ್ಲಿ ಕೀ ಸೇರಿಸಿ.",
}

# Scripted FAKE-model replies (machine-written; native-speaker review PENDING). Native script, numbers as words,
# no echo of the caller (an echo could carry STT digits into speech). Used only by FakeProvider (tests / E2E).
_FAKE_MSG = {
    "en": "Test model reply. Our branch opens at ten in the morning on Saturday.",
    "ja": "テスト用の応答です。土曜日は午前十時に開店します。",
    "hi": "यह परीक्षण उत्तर है। शनिवार को शाखा सुबह दस बजे खुलती है।",
    "bn": "এটি পরীক্ষার উত্তর। শনিবার শাখা সকাল দশটায় খোলে।",
    "kn": "ಇದು ಪರೀಕ್ಷಾ ಉತ್ತರ. ಶನಿವಾರ ಶಾಖೆ ಬೆಳಿಗ್ಗೆ ಹತ್ತು ಗಂಟೆಗೆ ತೆರೆಯುತ್ತದೆ.",
}


def _lang_from_messages(messages: list[dict]) -> tuple[str, str]:
    from agent.lang import dominant_language

    last = next((m for m in reversed(messages) if m["role"] == "user"), None)
    text = last["content"] if last and isinstance(last["content"], str) else ""
    if last and isinstance(last.get("content"), list):
        text = " ".join(b.get("text", "") for b in last["content"] if isinstance(b, dict))
    m = re.search(r"caller_language=(\w\w)", text)
    caller = text.split("</context>")[-1].strip()
    lang = m.group(1) if m else (dominant_language(caller)[0] or "en")
    return lang, caller


async def _noop(_chunk: str) -> None:
    return None


async def _emit(text: str, on_text: OnText | None) -> None:
    if on_text:
        for part in re.findall(r"\S+\s*", text):
            await on_text(part)
            await asyncio.sleep(0)


class DemoProvider(LLMProvider):
    name = "demo"

    async def stream(self, *, system, messages, model=None, max_tokens=300, tools=None, on_text=None,
                     purpose="reply", call_id=None) -> LLMResult:
        lang, _ = _lang_from_messages(messages)
        text = _DEMO_MSG.get(lang, _DEMO_MSG["en"])
        await _emit(text, on_text)
        return LLMResult(text=text, model="demo", stop_reason="end_turn", ttft_ms=0, total_ms=0)

    async def complete_json(self, **kw) -> dict:
        raise ValueError("demo mode: no language model configured")


class FakeProvider(LLMProvider):
    """Deterministic scripted provider for tests. `script` may be a callable(messages, system)->str|dict."""
    name = "fake"

    def __init__(self, script: Callable[[list[dict], str], Any] | None = None, json_script=None, delay_ms: int = 0):
        self.script = script
        self.json_script = json_script
        self.delay_ms = delay_ms
        self.calls: list[dict] = []

    async def stream(self, *, system, messages, model=None, max_tokens=300, tools=None, on_text=None,
                     purpose="reply", call_id=None) -> LLMResult:
        self.calls.append({"system": system, "messages": messages, "tools": tools, "purpose": purpose, "model": model})
        if self.delay_ms:
            await asyncio.sleep(self.delay_ms / 1000)
        if self.script:
            out = self.script(messages, system)
        else:
            lang, caller = _lang_from_messages(messages)
            out = _FAKE_MSG.get(lang, _FAKE_MSG["en"])
        if isinstance(out, dict) and out.get("tool"):
            tc = ToolCall("toolu_fake_%d" % len(self.calls), out["tool"], out.get("input", {}))
            return LLMResult(text=out.get("text", ""), model="fake", stop_reason="tool_use", tool_calls=[tc],
                             content=[{"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}])
        text = str(out)
        await _emit(text, on_text)
        return LLMResult(text=text, model="fake", stop_reason="end_turn", ttft_ms=0, total_ms=self.delay_ms)

    async def complete_json(self, *, system, prompt, model=None, max_tokens=400, purpose="json", call_id=None) -> dict:
        self.calls.append({"system": system, "prompt": prompt, "purpose": purpose})
        if self.json_script:
            out = self.json_script(prompt, system)
            if isinstance(out, Exception):
                raise out
            return out if isinstance(out, dict) else parse_json_object(str(out))
        raise ValueError("fake provider has no json_script")
