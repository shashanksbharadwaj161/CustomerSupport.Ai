"""M0 Claude reply quality per language: automatic checks + replies for native-speaker rating.

Automatic checks per reply: language (from script, never from the model), native script
(not romanized), no digits, at most 2 sentences, no markdown/emoji/URL. Also time to
first text and total latency, tokens, cost. A switch test sends turn 1 in language A,
turn 2 in language B, and checks reply 2 is in B.

  ANTHROPIC_API_KEY=... python -m eval.runners.run_llm --model claude-haiku-5-5 --max-usd 1
  python -m eval.runners.run_llm --model claude-sonnet-5-5 --langs kn bn   # fallback check

The Claude API is the project's only spend ($0 rule). Default is the quick set and a $0.50
cap; Haiku 5.5 is $0.10/$0.50 per million tokens. Stops at --max-usd.
Key: ANTHROPIC_API_KEY env for M0. From M1 the key comes from the encrypted settings store.
"""
from __future__ import annotations

import argparse
import itertools
import os
import re
import time

from agent.lang import LANGS, dominant_language, find_digits, is_native_script
from agent.llm.pricing import cost_usd
from agent.llm.prompt import build_system
from eval.common import EVAL, OUT, load_lines, percentile, save

PERSONA = "Name: Asha. Warm, calm, polite. Formal register in every language (Japanese: teineigo)."
_SENT = re.compile(r"[^.!?。！？।]+[.!?。！？।]+|[^.!?。！？।]+$")
_MD = re.compile(r"(\*\*|__|^#|^\s*[-*•]\s|`|https?://|www\.)", re.M)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def check_reply(reply: str, accept: list[str]) -> dict:
    lang, share = dominant_language(reply)
    expected = accept[0]
    sentences = [s for s in (m.strip() for m in _SENT.findall(reply)) if s]
    return {
        "reply_lang": lang, "lang_ok": lang in accept,
        "native_ok": is_native_script(reply, lang or expected) and lang in accept,
        "digits": "".join(find_digits(reply)), "no_digits": not find_digits(reply),
        "sentences": len(sentences), "short_ok": len(sentences) <= 2,
        "format_ok": not _MD.search(reply) and not _EMOJI.search(reply),
    }


class Runner:
    def __init__(self, model: str, effort: str, thinking: str, max_usd: float):
        import anthropic

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is not set (M0 reads it from the environment).")
        self.client = anthropic.Anthropic(api_key=key, max_retries=3)
        self.model, self.effort, self.thinking, self.max_usd = model, effort, thinking, max_usd
        self.spent = 0.0
        brief = (EVAL / "fixtures" / "site_brief.md").read_text(encoding="utf-8")
        # cached prefix: stable bytes only (the M0 prompt may be below the minimum cacheable size)
        self.system = [{"type": "text", "text": build_system(PERSONA, brief),
                        "cache_control": {"type": "ephemeral"}}]

    def ask(self, messages: list[dict]) -> dict:
        if self.spent >= self.max_usd:
            raise RuntimeError("spend cap reached")
        kw = dict(model=self.model, max_tokens=400, system=self.system, messages=messages,
                  output_config={"effort": self.effort})
        if self.thinking == "off":
            kw["thinking"] = {"type": "disabled"}  # allowed at effort high or below on Haiku 5.5
        t0 = time.perf_counter()
        ttft = None
        with self.client.messages.stream(**kw) as stream:
            for _ in stream.text_stream:
                if ttft is None:
                    ttft = time.perf_counter() - t0
            msg = stream.get_final_message()
        total = time.perf_counter() - t0
        c = cost_usd(self.model, msg.usage)
        self.spent += c
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        return {"reply": text, "stop_reason": msg.stop_reason,
                "ttft_ms": round(ttft * 1000) if ttft else None, "total_ms": round(total * 1000),
                "in_tok": msg.usage.input_tokens, "out_tok": msg.usage.output_tokens,
                "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
                "usd": round(c, 6), "request_id": getattr(msg, "_request_id", None)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--effort", default="low", choices=["low", "medium", "high"])
    ap.add_argument("--thinking", default="off", choices=["off", "adaptive"])
    ap.add_argument("--langs", nargs="*")
    ap.add_argument("--max-usd", type=float, default=0.50)
    ap.add_argument("--set", default="quick", choices=["quick", "full"],
                    help="quick (default, cheapest): 3 lines per language + 2 mixed + 4 switch pairs; full: all 60 + 20 pairs")
    ap.add_argument("--no-switch", action="store_true")
    a = ap.parse_args(argv)

    import anthropic

    r = Runner(a.model, a.effort, a.thinking, a.max_usd)
    rows, switch_rows = [], []
    try:
        lines = load_lines(a.langs)
        if a.set == "quick":
            lines = ([l for l in lines if l["category"] == "mono" and int(l["id"][-2:]) in (3, 6, 10)]
                     + [l for l in lines if l["id"] in ("mx_01", "mx_05")])
        for line in lines:
            res = r.ask([{"role": "user", "content": line["text"]}])
            res.update(check_reply(res["reply"], line["accept"]))
            res.update(id=line["id"], lang=line["lang"], category=line["category"], text=line["text"])
            rows.append(res)
            print(f"{line['id']} [{res['reply_lang']}] {res['ttft_ms']} ms | {res['reply']}")
        if not a.no_switch:
            mono = {l: [x for x in load_lines([l], include_mixed=False)] for l in (a.langs or LANGS)}
            pairs = list(itertools.permutations(mono, 2))
            if a.set == "quick":
                pairs = [p for p in pairs if p in {("en", "hi"), ("hi", "kn"), ("kn", "bn"), ("bn", "ja")}]
            for la, lb in pairs:
                first, second = mono[la][2], mono[lb][9]  # branch hours -> ask for a human
                r1 = r.ask([{"role": "user", "content": first["text"]}])
                r2 = r.ask([{"role": "user", "content": first["text"]},
                            {"role": "assistant", "content": r1["reply"] or "..."},
                            {"role": "user", "content": second["text"]}])
                r2.update(check_reply(r2["reply"], [lb]))
                r2.update(pair=f"{la}->{lb}", turn1_reply=r1["reply"])
                switch_rows.append(r2)
                print(f"switch {la}->{lb} [{r2['reply_lang']}] | {r2['reply']}")
    except RuntimeError as e:
        print(f"stopped: {e}")
    except anthropic.APIStatusError as e:
        print(f"API error {e.status_code}: stopping (request id {getattr(e, 'request_id', None)})")

    def rate(rs, k):
        return round(sum(bool(x[k]) for x in rs) / len(rs), 3) if rs else None

    per_lang = {}
    for lang in sorted({x["lang"] for x in rows}):
        rs = [x for x in rows if x["lang"] == lang]
        per_lang[lang] = {"n": len(rs), **{k: rate(rs, k) for k in
                          ("lang_ok", "native_ok", "no_digits", "short_ok", "format_ok")},
                          "ttft_p50_ms": percentile([x["ttft_ms"] for x in rs if x["ttft_ms"]], 0.5),
                          "ttft_p90_ms": percentile([x["ttft_ms"] for x in rs if x["ttft_ms"]], 0.9),
                          "refusals": sum(x["stop_reason"] == "refusal" for x in rs)}
    tag = f"llm_{a.model}_{a.effort}_{a.thinking}_{a.set}"
    manifest = [{"type": "llm", "item_id": f"{tag}/{x['id']}", "lang": x["lang"],
                 "prompt": x["text"], "text": x["reply"]} for x in rows]
    (OUT / f"{tag}_manifest.json").parent.mkdir(parents=True, exist_ok=True)
    import json

    (OUT / f"{tag}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    p = save(tag, {"kind": "llm", "model": a.model, "effort": a.effort, "thinking": a.thinking,
                   "spent_usd": round(r.spent, 4), "per_lang": per_lang,
                   "mixed": {k: rate([x for x in rows if x["category"] != "mono"], k)
                             for k in ("lang_ok", "native_ok")},
                   "switch": {"n": len(switch_rows), "lang_ok": rate(switch_rows, "lang_ok"),
                              "failures": [x["pair"] for x in switch_rows if not x["lang_ok"]]},
                   "rows": rows, "switch_rows": switch_rows})
    print(f"spent ${r.spent:.4f}; saved {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
