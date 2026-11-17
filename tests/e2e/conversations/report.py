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
import subprocess
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
             f"- Full video: shaon-conversation-{run['lang']}-full.mp4 ({ev['duration_s']} s, 1280x720, H.264/AAC, unedited)",
             f"- 30-s excerpt: shaon-conversation-{run['lang']}.mp4 = {ev['excerpt']['start_s']}-{ev['excerpt']['end_s']} s of the full file, "
             "one contiguous cut, labelled EXCERPT on screen",
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


EXCERPT_S = 30.0
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def full_path(lang: str) -> pathlib.Path:
    """The unedited recording. Older runs wrote it as shaon-conversation-xx.mp4: move it to -full.mp4 first."""
    full, short = OUT / f"shaon-conversation-{lang}-full.mp4", OUT / f"shaon-conversation-{lang}.mp4"
    if short.exists() and (not full.exists() or short.stat().st_mtime > full.stat().st_mtime) \
            and "EXCERPT" not in subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=title", "-of", "csv=p=0",
                                                 str(short)], capture_output=True, text=True).stdout:
        short.replace(full)
    return full


def make_excerpt(run: dict) -> dict:
    """ONE contiguous 30-s cut of the unedited recording (no internal edits, latency kept), labelled EXCERPT on screen.

    Window: from the start of the call (AI disclosure greeting) when the first answer finishes inside 30 s, otherwise
    the 30 s that end just after the first answer (customer question + the real wait + the answer)."""
    lang = run["lang"]
    full, out = full_path(lang), OUT / f"shaon-conversation-{lang}.mp4"
    ev = {}
    for e in run["log"]:
        ev.setdefault(e["ev"], []).append(e["t"])
    rs = ev["record_start"][0]
    dur = run["probe"]["duration_s"]
    a1 = ev["agent_done"][0] - rs + 0.8
    start = 0.0 if a1 <= EXCERPT_S else min(a1 - EXCERPT_S, ev["customer_start"][0] - rs - 0.5)
    start = max(0.0, min(start, dur - EXCERPT_S))
    end = min(dur, start + EXCERPT_S)
    label = (f"EXCERPT  {start:.1f}s-{end:.1f}s of the unedited {dur:.1f}s recording  "
             f"(shaon-conversation-{lang}-full.mp4)  live call, not sped up")
    vf = (f"drawbox=x=0:y=ih-30:w=iw:h=30:color=black@0.72:t=fill,"
          f"drawtext=fontfile={FONT}:text='{label}':fontcolor=white:fontsize=17:x=12:y=h-23")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(full), "-t", f"{end - start:.2f}",
                    "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-metadata", f"title=EXCERPT of shaon-conversation-{lang}-full.mp4 ({start:.1f}-{end:.1f}s)", "-movflags", "+faststart",
                    str(out)], check=True)
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)],
                                  capture_output=True, text=True).stdout)
    vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    mx = next((float(ln.split(":")[-1].replace("dB", "")) for ln in vol.splitlines() if "max_volume" in ln), None)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), {})
    return {"file": out.name, "full_file": full.name, "start_s": round(start, 1), "end_s": round(end, 1),
            "duration_s": round(float(j["format"]["duration"]), 2), "width": v["width"], "height": v["height"],
            "video_codec": v["codec_name"], "audio_codec": a.get("codec_name"), "max_db": mx}


def main() -> int:
    runs = [json.loads(p.read_text()) for p in sorted(OUT.glob("run-*.json"))]
    order = ["en", "hi", "bn", "kn", "ja"]
    runs.sort(key=lambda r: order.index(r["lang"]))
    evs = []
    for r in runs:
        ev = evaluate(r)
        ev["excerpt"] = make_excerpt(r)
        evs.append(ev)
        (OUT / f"transcript-{r['lang']}.md").write_text(transcript_md(r, ev), encoding="utf-8")
    hdr = "| Language | Result | Agent replies | Agent voice | Customer voice | STT | First audio (ms) | Audio errors | Full duration | 30-s excerpt |"
    rows = [hdr, "|" + "---|" * 10]
    for e in evs:
        rows.append(f"| {e['language']} | {'PASS' if e['pass'] else 'FAIL'} | {e['provider']} ({e['model_served']}) | "
                    f"{', '.join(e['agent_voices_used'])} | {e['customer_voice']} | {e['stt']} | {e['first_audio_ms']} | "
                    f"{e['audio_errors']} | {e['duration_s']} s | {e['excerpt']['start_s']}-{e['excerpt']['end_s']} s |")
    fails = [f"- {e['language']}: {'; '.join(e['why'])}" for e in evs if not e["pass"]]
    md = ("# ShaOn two-speaker website recordings\n\nRecorded on a CPU-only cloud machine (4 cores, no GPU): Xvfb + PulseAudio + "
          "headed Chromium on the real /call/ page + ffmpeg (screen and audio in one process, unedited). "
          "shaon-conversation-xx.mp4 is a labelled 30-s EXCERPT (one contiguous cut); the -full.mp4 file is the whole unedited call. "
          "First audio = customer stopped speaking -> first agent audio played in the browser. Agent replies: "
          "SCRIPTED test provider (no Anthropic key on this machine): real Claude conversations are PENDING.\n\n"
          + "\n".join(rows) + "\n\n" + ("Failures:\n" + "\n".join(fails) + "\n" if fails else "All languages passed every check.\n"))
    (OUT / "results.md").write_text(md, encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(evs, ensure_ascii=False, indent=1), encoding="utf-8")
    with zipfile.ZipFile(OUT / "shaon-conversations.zip", "w", zipfile.ZIP_STORED) as z:
        for r in runs:
            for n in (f"shaon-conversation-{r['lang']}.mp4", f"shaon-conversation-{r['lang']}-full.mp4"):
                z.write(OUT / n, n)
            z.write(OUT / f"transcript-{r['lang']}.md", f"transcript-{r['lang']}.md")
        z.write(OUT / "results.md", "results.md")
        z.write(OUT / "results.json", "results.json")
    print(md)
    return 0 if all(e["pass"] for e in evs) else 1


if __name__ == "__main__":
    sys.exit(main())
