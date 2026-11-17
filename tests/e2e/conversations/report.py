#!/usr/bin/env python3
"""Turn the recording runs (eval/out/conversations/run-*.json + mp4) into transcripts, a results table and a ZIP.

PASS needs ALL of: each agent answer fits the question asked (scripted mode: hours, then lost card); 1280x720 H.264 video with an AAC audio track; both customer lines audible in the recording
(max level > -35 dBFS); the greeting and both agent answers audible; the greeting finished before the customer spoke;
two customer turns recognised in the right language; two meaningful agent answers (not the "did not catch that" reply)
in the right native script; no TTS / pipeline error events. Anything else is FAIL with the reason.
"""
from __future__ import annotations

import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "eval" / "out" / "conversations"
NAMES = {"en": "English", "hi": "Hindi", "bn": "Bengali", "kn": "Kannada", "ja": "Japanese"}
AUDIBLE = -35.0


def evaluate(run: dict) -> dict:
    from agent.lang.script import dominant_language
    from agent.llm.scripted import REPLIES
    lang, pr = run["lang"], run["probe"]
    ms = run["messages"]
    users = [m for m in ms if m["event"] == "transcript" and m["role"] == "user"]
    agents = [m for m in ms if m["event"] == "transcript" and m["role"] == "agent"]
    answers = [m for m in agents if not m.get("greeting")][: len(users) or 2]
    tts = [m for m in ms if m["event"] == "tts"]
    errors = [m for m in ms if m["event"] in ("error", "tts_unavailable")]
    log = {}
    for e in run["log"]:
        log.setdefault(e["ev"], []).append(e)
    fails = []
    if (pr.get("width"), pr.get("height")) != (1280, 720) or pr.get("video_codec") != "h264":
        fails.append(f"video {pr.get('width')}x{pr.get('height')} {pr.get('video_codec')}")
    if pr.get("audio_codec") != "aac":
        fails.append("no AAC audio track")
    cw = pr["windows"]["customer"]
    if len(cw) < 2 or any(w.get("max_volume", -99) < AUDIBLE for w in cw):
        fails.append(f"customer audio not audible: {cw}")
    aw = pr["windows"]["agent"]
    if len(aw) < 3 or any(w.get("max_volume", -99) < AUDIBLE for w in aw[:3]):
        fails.append(f"agent audio not audible in every window: {[w.get('max_volume') for w in aw]}")
    if not all(e.get("ok") for e in log.get("greeting_done", []) + log.get("agent_done", [])):
        fails.append("an agent turn did not finish in time")
    ok_users = [u for u in users if u.get("lang") == lang and (u.get("text") or "").strip()]
    if len(ok_users) < 2:
        fails.append(f"customer turns recognised in {lang}: {len(ok_users)} of {len(users)}")
    good = [a for a in answers if a.get("text") and dominant_language(a["text"])[0] == lang]
    if len(good) < 2:
        fails.append(f"native-script answers: {len(good)}")
    if run.get("provider") == "scripted":  # the answer must fit the QUESTION (turn 1: hours, turn 2: lost card)
        for k, (want, a) in enumerate(zip(("hours", "card"), answers)):
            if (a.get("text") or "") != REPLIES[want][lang]:
                fails.append(f"answer {k + 1} does not answer the {want} question: {a.get('text', '')[:60]}")
    if len(users) > 2:
        fails.append(f"{len(users)} customer turns detected for 2 spoken lines (a line was split)")
    if errors:
        fails.append(f"error events: {[e.get('detail') or e.get('stage') for e in errors][:3]}")
    fa = [t.get("first_audio_ms") for t in run.get("turns", []) if t.get("first_audio_ms")]
    stt = sorted({e.split(":")[0] + (":" + e.split(":")[1] if e.split(":")[1] else "") for u in users for e in (u.get("engines") or [])})
    served = sorted({t.get("model_served") or "?" for t in run.get("turns", [])})
    return {
        "lang": lang, "language": NAMES[lang], "pass": not fails, "why": fails,
        "provider": run.get("provider"), "model_served": ", ".join(served),
        "customer_voice": run.get("customer_voice"), "agent_voice": run.get("agent_voice"),
        "agent_voices_used": sorted({f"{t.get('voice')} ({t.get('engine')})" for t in tts}),
        "stt": ", ".join(stt) or "see server log", "first_audio_ms": fa,
        "stt_ms": [u.get("stt_ms") for u in users], "duration_s": pr["duration_s"],
        "audio_errors": len(errors), "customer_max_db": [w.get("max_volume") for w in cw],
        "agent_max_db": [w.get("max_volume") for w in aw],
    }


def transcript_md(run: dict, ev: dict) -> str:
    rs = next(e["t"] for e in run["log"] if e["ev"] == "record_start")
    lines = [f"# ShaOn conversation, {ev['language']} ({run['lang']})", "",
             f"- Video: shaon-conversation-{run['lang']}.mp4 ({ev['duration_s']} s, 1280x720, H.264/AAC, unedited)",
             f"- Agent replies: {ev['provider']} provider, model reported: {ev['model_served']}"
             + (" (SCRIPTED test replies from the fake demo site, NOT Claude)" if ev["provider"] == "scripted" else ""),
             f"- Agent voice: {', '.join(ev['agent_voices_used'])}; customer voice: {ev['customer_voice']} (synthetic test customer)",
             f"- Speech recognition: {ev['stt']}; first agent audio after the customer stopped (ms): {ev['first_audio_ms']}",
             f"- Result: {'PASS' if ev['pass'] else 'FAIL: ' + '; '.join(ev['why'])}", "",
             "## What the customer said (script, synthesised)", ""]
    lines += [f"{i + 1}. {t}" for i, t in enumerate(run.get("customer_lines", []))]
    lines += ["", "## Live transcript as shown on the page (recognised / spoken)", ""]
    marks = {e["ev"] + str(e.get("turn", "")): round(e["t"] - rs, 1) for e in run["log"]}
    for m in run["messages"]:
        if m["event"] == "transcript":
            who = "Customer (recognised)" if m["role"] == "user" else "Agent"
            lines.append(f"- **{who}** [{m.get('lang')}]: {m.get('text')}")
    lines += ["", "## Timeline (seconds into the video)", ""]
    lines += [f"- {k}: {v}" for k, v in marks.items() if k not in ("geometry",)]
    return "\n".join(lines) + "\n"


def main() -> int:
    runs = [json.loads(p.read_text()) for p in sorted(OUT.glob("run-*.json"))]
    order = ["en", "hi", "bn", "kn", "ja"]
    runs.sort(key=lambda r: order.index(r["lang"]))
    evs = []
    for r in runs:
        ev = evaluate(r)
        evs.append(ev)
        (OUT / f"transcript-{r['lang']}.md").write_text(transcript_md(r, ev), encoding="utf-8")
    hdr = "| Language | Result | Agent replies | Agent voice | Customer voice | STT | First audio (ms) | Audio errors | Duration |"
    rows = [hdr, "|" + "---|" * 9]
    for e in evs:
        rows.append(f"| {e['language']} | {'PASS' if e['pass'] else 'FAIL'} | {e['provider']} ({e['model_served']}) | "
                    f"{', '.join(e['agent_voices_used'])} | {e['customer_voice']} | {e['stt']} | {e['first_audio_ms']} | "
                    f"{e['audio_errors']} | {e['duration_s']} s |")
    fails = [f"- {e['language']}: {'; '.join(e['why'])}" for e in evs if not e["pass"]]
    md = ("# ShaOn two-speaker website recordings\n\nRecorded on a CPU-only cloud machine (4 cores, no GPU): Xvfb + PulseAudio + "
          "headed Chromium on the real /call/ page + ffmpeg (screen and audio in one process, unedited). Agent replies: "
          "SCRIPTED test provider (no Anthropic key on this machine): real Claude conversations are PENDING.\n\n"
          + "\n".join(rows) + "\n\n" + ("Failures:\n" + "\n".join(fails) + "\n" if fails else "All languages passed every check.\n"))
    (OUT / "results.md").write_text(md, encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(evs, ensure_ascii=False, indent=1), encoding="utf-8")
    with zipfile.ZipFile(OUT / "shaon-conversations.zip", "w", zipfile.ZIP_STORED) as z:
        for r in runs:
            z.write(OUT / f"shaon-conversation-{r['lang']}.mp4", f"shaon-conversation-{r['lang']}.mp4")
            z.write(OUT / f"transcript-{r['lang']}.md", f"transcript-{r['lang']}.md")
        z.write(OUT / "results.md", "results.md")
        z.write(OUT / "results.json", "results.json")
    print(md)
    return 0 if all(e["pass"] for e in evs) else 1


if __name__ == "__main__":
    sys.exit(main())
