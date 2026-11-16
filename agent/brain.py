"""Turn engine: one caller turn in, spoken sentences out. Independent of Pipecat (unit-testable).

Steps per turn (PLAN.md sections 6, 8, 9):
  guard_in (local rules) -> retrieval -> LLM (stream, tools) -> sentence split ->
  reply language from script -> guard_out (local rules + optional combined model check) -> sentences.
Every step's time is measured; nothing is estimated.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from agent.lang import dominant_language
from agent.llm.prompt import build_system, turn_context
from agent.llm.provider import LLMProvider
from agent.logscrub import scrub
from agent.tools import run_tool, specs_for

Emit = Callable[[str, dict], Awaitable[None]]
# CJK full stops end a sentence without a following space; Latin/Indic ones need whitespace or end of text
_SENT_END = re.compile(r"(.+?(?:[。！？]+|[.!?।॥]+(?=\s|$))[\"'」』)]*)\s*", re.S)


@dataclass
class GuardVerdict:
    action: str = "allow"  # allow | block | handoff
    rule: str | None = None
    detail: str | None = None
    stage: str = "input"


class Guard(Protocol):
    def check_input(self, text: str, lang: str, profile: dict) -> GuardVerdict: ...
    def check_reply_local(self, text: str, lang: str, profile: dict, user_text: str) -> GuardVerdict: ...
    async def check_reply_model(self, text: str, lang: str, profile: dict, user_text: str,
                                passages: list[dict], provider: LLMProvider, call_id: str | None) -> GuardVerdict: ...
    def needs_model_check(self, profile: dict, provider: LLMProvider) -> bool: ...


class Retriever(Protocol):
    def search(self, text: str, profile: dict, k: int) -> list[dict]: ...


class NoGuard:
    def check_input(self, text, lang, profile): return GuardVerdict()
    def check_reply_local(self, text, lang, profile, user_text): return GuardVerdict(stage="reply")
    async def check_reply_model(self, *a, **k): return GuardVerdict(stage="reply")
    def needs_model_check(self, profile, provider): return False


@dataclass
class CallContext:
    call_id: str
    profile: dict
    brief: str | None = None
    kb_text: str | None = None
    history: list[dict] = field(default_factory=list)
    current_lang: str = "en"
    override_lang: str | None = None
    voice_by_lang: dict[str, str] = field(default_factory=dict)
    max_history: int = 12

    def system_prompt(self) -> str:
        return build_system(self.profile, self.brief if self.profile["knowledge"].get("site_brief", True) else None,
                            self.kb_text)

    def model_for(self, lang: str, default: str) -> str:
        return self.profile["languages"].get("llm_model_override", {}).get(lang) or default


def split_sentences(buf: str) -> tuple[list[str], str]:
    """Complete sentences found in buf, and the remainder."""
    out, pos = [], 0
    for m in _SENT_END.finditer(buf):
        s = m.group(1).strip()
        if s:
            out.append(s)
        pos = m.end()
    return out, buf[pos:]


class TurnEngine:
    def __init__(self, ctx: CallContext, provider: LLMProvider, model: str, guard: Guard | None = None,
                 retriever: Retriever | None = None, log_guard: Callable[[GuardVerdict], None] | None = None):
        self.ctx, self.provider, self.model = ctx, provider, model
        self.guard = guard or NoGuard()
        self.retriever = retriever
        self.log_guard = log_guard or (lambda v: None)

    def handoff_text(self, lang: str) -> str:
        return self.ctx.profile["guardrails"]["handoff_message"].get(lang) or self.ctx.profile["guardrails"]["handoff_message"]["en"]

    async def respond(self, user_text: str, lang: str, emit: Emit) -> dict:
        """Run one turn. Emits 'sentence' events in order; returns timing/metadata for the turn log."""
        p = self.ctx.profile
        t0 = time.perf_counter()
        meta: dict[str, Any] = {"lang": lang, "guard": [], "sources": [], "provider": self.provider.name,
                                "model": None, "llm_ttft_ms": None, "llm_ms": None, "guard_ms": 0}
        user_text = scrub(user_text)

        g = self.guard.check_input(user_text, lang, p)
        meta["guard"].append(g.__dict__)
        if g.action != "allow":
            self.log_guard(g)
            await emit("guardrail", g.__dict__)
            await self._speak_fixed(self.handoff_text(lang), lang, emit, meta, handoff=True)
            self._remember(user_text, self.handoff_text(lang))
            return meta

        passages: list[dict] = []
        if self.retriever and p["knowledge"].get("source_ids"):
            tr = time.perf_counter()
            try:
                passages = self.retriever.search(user_text, p, int(p["knowledge"].get("top_k", 4)))
            except Exception as e:  # retrieval failure must not kill the call
                await emit("warning", {"stage": "retrieval", "error": str(e)[:200]})
            meta["retrieval_ms"] = round((time.perf_counter() - tr) * 1000)
            meta["sources"] = [{"url": x.get("url"), "title": x.get("title"), "score": x.get("score")} for x in passages]
            if meta["sources"]:
                await emit("sources", {"sources": meta["sources"]})

        model = self.ctx.model_for(lang, self.model)
        meta["model"] = model
        messages = self.ctx.history[-self.ctx.max_history:] + [
            {"role": "user", "content": turn_context(lang, passages) + user_text}]
        buffered = self.guard.needs_model_check(p, self.provider)
        spoken: list[str] = []
        buf = ""
        first_text_t = None

        async def on_text(chunk: str):
            nonlocal buf, first_text_t
            if first_text_t is None:
                first_text_t = time.perf_counter()
            buf += chunk
            sents, buf = split_sentences(buf)
            for s in sents:
                spoken.append(s)
                if not buffered:
                    await self._emit_sentence(s, lang, emit, meta)

        tools = specs_for(p.get("tools", [])) or None
        result = await self.provider.stream(system=self.ctx.system_prompt(), messages=messages, model=model,
                                            tools=tools, on_text=on_text, call_id=self.ctx.call_id)
        rounds = 0
        while result.tool_calls and rounds < 2:
            rounds += 1
            tool_results = []
            for tc in result.tool_calls:
                out = run_tool(tc.name, tc.input, p.get("tools", []))
                meta.setdefault("tools", []).append({"name": tc.name, "input": tc.input, "output": out})
                await emit("tool", {"name": tc.name, "blocked": bool(out.get("blocked"))})
                tool_results.append({"type": "tool_result", "tool_use_id": tc.id, "content": _json(out)})
            messages = messages + [{"role": "assistant", "content": result.content},
                                   {"role": "user", "content": tool_results}]
            result = await self.provider.stream(system=self.ctx.system_prompt(), messages=messages, model=model,
                                                tools=tools, on_text=on_text, call_id=self.ctx.call_id)
        tail = buf.strip()
        if tail:
            spoken.append(tail)
            if not buffered:
                await self._emit_sentence(tail, lang, emit, meta)
        meta["llm_ms"] = round((time.perf_counter() - t0) * 1000)
        meta["llm_ttft_ms"] = round((first_text_t - t0) * 1000) if first_text_t else None
        reply = " ".join(spoken).strip()

        if result.refused or not reply:
            v = GuardVerdict("handoff", "model_refusal" if result.refused else "empty_reply", stage="reply")
            meta["guard"].append(v.__dict__)
            self.log_guard(v)
            await emit("guardrail", v.__dict__)
            if not meta.get("sentences"):
                await self._speak_fixed(self.handoff_text(lang), lang, emit, meta, handoff=True)
            self._remember(user_text, self.handoff_text(lang))
            return meta

        tg = time.perf_counter()
        v = self.guard.check_reply_local(reply, lang, p, user_text)
        if v.action == "allow" and buffered:
            v = await self.guard.check_reply_model(reply, lang, p, user_text, passages, self.provider, self.ctx.call_id)
        meta["guard_ms"] = round((time.perf_counter() - tg) * 1000)
        meta["guard"].append(v.__dict__)
        if v.action != "allow":
            self.log_guard(v)
            await emit("guardrail", v.__dict__)
            if buffered or not meta.get("sentences"):
                await self._speak_fixed(self.handoff_text(lang), lang, emit, meta, handoff=True)
            else:  # already spoken (unbuffered mode): follow with the handoff
                await self._speak_fixed(self.handoff_text(lang), lang, emit, meta, handoff=True)
            self._remember(user_text, self.handoff_text(lang))
            return meta
        if buffered:
            for s in spoken:
                await self._emit_sentence(s, lang, emit, meta)
        self._remember(user_text, reply)
        meta["reply"] = reply
        meta["reply_lang"] = dominant_language(reply)[0] or lang
        return meta

    async def _emit_sentence(self, s: str, turn_lang: str, emit: Emit, meta: dict):
        lang = dominant_language(s)[0] or turn_lang  # reply language from script, never from the model
        meta.setdefault("sentences", []).append({"text": s, "lang": lang})
        await emit("sentence", {"text": s, "lang": lang})

    async def _speak_fixed(self, text: str, lang: str, emit: Emit, meta: dict, handoff=False):
        meta.setdefault("sentences", []).append({"text": text, "lang": lang, "handoff": handoff})
        meta["handoff"] = handoff or meta.get("handoff", False)
        meta["reply"] = text
        meta["reply_lang"] = lang
        await emit("sentence", {"text": text, "lang": lang, "handoff": handoff})

    def _remember(self, user_text: str, reply: str):
        self.ctx.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]


def _json(o) -> str:
    import json
    return json.dumps(o, ensure_ascii=False)
