"""Live-call E2E for Hindi, Bengali, Kannada (+ switches hi->en, bn->ja, kn->hi inside one call), $0:
real FLEURS speech (CC-BY-4.0) as the caller through Chromium's fake microphone -> real VAD/LID/STT routing ->
scripted FAKE LLM (machine-written native-script lines, native review pending) -> CPU TTS -> browser.

  python tests/e2e/run_indic_e2e.py            # needs: [app,stt-whisper,tts-kokoro] + transformers (MMS), web build, Chromium
Per turn it asserts: language detected = expected, STT engine = the first usable engine in engines.json order,
reply language (from script) = expected, TTS produced audio (no tts_unavailable), no digits in the reply, timings present.
Writes tests/e2e/results/indic_*.json and eval/out/indic_e2e.json (for the reports). Audio stays outside the repo.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from eval.fleurs import CACHE, fetch  # noqa: E402

OUT = ROOT / "tests" / "e2e" / "results"
WAV = CACHE.parent / "e2e"
PORT = int(os.environ.get("E2E_PORT", "8768"))
CASES = [("hi",), ("bn",), ("kn",), ("hi", "en"), ("bn", "ja"), ("kn", "hi")]
DIGITS = re.compile(r"[0-9०-९০-৯೦-೯０-９]")


def clip_for(lang: str) -> dict:
    """Shortest of the first 10 seeded FLEURS clips (deterministic, not cherry-picked by result)."""
    clips = fetch(lang, 10)
    return min(clips, key=lambda c: c["seconds"])


def build_wav(langs: tuple, gap_s: float = 22.0) -> tuple[pathlib.Path, list[dict]]:
    WAV.mkdir(parents=True, exist_ok=True)
    sr = 16000
    parts, used = [np.zeros(int(sr * 1.5), dtype=np.float32)], []
    for i, l in enumerate(langs):
        c = clip_for(l)
        a, s = sf.read(c["wav"], dtype="float32")
        assert s == sr
        parts.append(a)
        parts.append(np.zeros(int(sr * (gap_s if i < len(langs) - 1 else 60)), dtype=np.float32))
        used.append(c)
    path = (WAV / f"call_{'_'.join(langs)}.wav").resolve()  # absolute, no ".." (Chrome ignores those)
    sf.write(path, np.concatenate(parts), sr, subtype="PCM_16")
    return path, used


def intended_stt(lang: str) -> str:
    from agent.engines import EngineManager
    em = EngineManager()
    return em.stt_route(lang)[0]


def check(langs, res) -> dict:
    users = res["user"]
    groups, cur = [], None  # agent sentences that follow each caller turn, in order
    for m in res.get("ordered", []):
        if m["role"] == "user":
            cur = []
            groups.append(cur)
        elif cur is not None and not m["greeting"]:
            cur.append(m)
    turns = []
    for i, want in enumerate(langs):
        u = users[i] if i < len(users) else {}
        a = groups[i] if i < len(groups) else []
        eng = (u.get("engines") or [""])[-1].split(":")[0]
        want_eng = intended_stt(want)
        tts = [t for t in res["tts"] if t["lang"] == want]
        reply = " ".join(x["text"] for x in a)
        t = {"want": want, "detected": u.get("lang"), "reason": u.get("reason"), "stt_engine": eng, "intended_stt": want_eng,
             "routing": u.get("routing"), "fallbacks": u.get("fallbacks"), "stt_ms": u.get("stt_ms"), "user_text": u.get("text"),
             "reply": reply, "reply_lang": a[0]["lang"] if a else None, "tts_voice": tts[0]["voice"] if tts else None,
             "tts_gen_ms": tts[0]["gen_ms"] if tts else None, "first_audio_ms": (res["turns"][i] if i < len(res["turns"]) else {}).get("first_audio_ms")}
        t["checks"] = {
            "language_detected": t["detected"] == want,
            "stt_routed_as_configured": eng == want_eng,
            "reply_language_from_script": t["reply_lang"] == want,
            "tts_produced_audio": bool(tts) and want not in res.get("tts_unavailable", []),
            "no_digits_in_reply": bool(reply) and not DIGITS.search(reply),
            "timings_present": t["stt_ms"] is not None and t["first_audio_ms"] is not None,
        }
        t["pass"] = all(t["checks"].values())
        turns.append(t)
    return {"case": "->".join(langs), "pass": all(t["pass"] for t in turns) and not res["errors"], "turns": turns, "errors": res["errors"],
            "wall_s": res["wall_s"]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    py = os.environ.get("PYTHON") or sys.executable
    env = {**os.environ, "SHAON_DATA_DIR": tempfile.mkdtemp(), "SHAON_LLM_PROVIDER": "fake", "SHAON_SEED_DEMO": "0",
           "SHAON_PRELOAD": "stt:en,stt:hi,lid,tts:en,tts:ja,tts:hi,tts:bn,tts:kn"}
    log = open(OUT / "indic_server.log", "w")
    srv = subprocess.Popen([py, "-m", "uvicorn", "--factory", "api.main:create_app", "--port", str(PORT), "--log-level", "warning"],
                           cwd=ROOT, env=env, stdout=log, stderr=log)
    results = []
    try:
        for _ in range(90):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        print("server up; waiting for model preload (MMS STT is ~4 GB)...")
        for _ in range(120):  # until MMS STT + TTS report loaded
            e = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/engines").read())["engines"]
            if e.get("mms", {}).get("loaded") and e.get("mms-tts", {}).get("loaded"):
                break
            time.sleep(3)
        time.sleep(10)
        for langs in CASES:
            wav, used = build_wav(langs)
            cmd = ["node", "scripts/call_e2e.mjs", f"http://127.0.0.1:{PORT}", str(wav), "websocket", "off", ".", "."]
            r = subprocess.run(cmd, cwd=ROOT / "web", env={**os.environ, "WAIT_TURNS": str(len(langs))}, capture_output=True, text=True, timeout=600)
            try:
                res = json.loads(r.stdout)
            except Exception:
                res = {"user": [], "agent": [], "tts": [], "turns": [], "errors": [r.stdout[-300:] + r.stderr[-300:]], "wall_s": None}
            c = check(langs, res)
            c["clips"] = [{"id": u["id"], "seconds": u["seconds"], "ref": u["text"]} for u in used]
            results.append(c)
            (OUT / f"indic_{'_'.join(langs)}.json").write_text(json.dumps({"check": c, "raw": res}, ensure_ascii=False, indent=1))
            print(f"{c['case']:<8} {'PASS' if c['pass'] else 'FAIL'}",
                  " | ".join(f"{t['want']}: det={t['detected']} stt={t['stt_engine']} tts={t['tts_voice']} first_audio={t['first_audio_ms']}"
                             + ("" if t["pass"] else f" FAILED {[k for k, v in t['checks'].items() if not v]}") for t in c["turns"]))
    finally:
        srv.terminate()
        srv.wait(timeout=30)
    from eval.common import save
    save("indic_e2e", {"kind": "indic_e2e", "note": "FLEURS read speech as caller; scripted fake LLM (machine-written lines, native review pending); CPU engines; one run each.",
                       "cases": results, "pass_rate": round(sum(c["pass"] for c in results) / len(results), 3)})
    sys.exit(0 if all(c["pass"] for c in results) else 1)


if __name__ == "__main__":
    main()
