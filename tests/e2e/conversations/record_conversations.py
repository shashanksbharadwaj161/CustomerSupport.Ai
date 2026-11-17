#!/usr/bin/env python3
"""Record real two-speaker calls with the ShaOn website (one per language) as screen recordings with audio.

What runs (nothing is edited or faked afterwards):
  - Xvfb display :99 (1280x720) + PulseAudio with two virtual sinks: "customer" (its monitor is the browser microphone)
    and "callmix" (browser speaker output; the customer sink is looped into it so the recording hears both voices).
  - The ShaOn server in local preview with the CPU engines; replies come from the SCRIPTED test provider unless a real
    Anthropic key is configured for this server (this script never reads or copies a key).
  - web/scripts/conversation_record.mjs: headed Chromium on the real /call/ page, ffmpeg x11grab + pulse in ONE process,
    and the synthetic CUSTOMER who speaks each line (distinct voice from scripts.json) after the agent finished talking.
  - Checks: ffprobe streams/duration/size, audio loudness per customer/agent window, transcript scripts.

  python tests/e2e/conversations/record_conversations.py [en hi bn kn ja]     -> eval/out/conversations/
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "eval" / "out" / "conversations"
PORT = 8460
PY = sys.executable
ENV_BASE = {**os.environ, "DISPLAY": ":99", "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", "/tmp/claude-0/xdg")}


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)


def ensure_display_and_audio():
    if sh("xdpyinfo -display :99 >/dev/null 2>&1 || pgrep -f 'Xvfb :99'").returncode != 0:
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1280x900x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
    os.makedirs(ENV_BASE["XDG_RUNTIME_DIR"], exist_ok=True)
    if sh("pactl info", env=ENV_BASE).returncode != 0:
        sh(["pulseaudio", "-n", "--daemonize=yes", "--exit-idle-time=-1", "--disallow-exit",
            "-L", "module-native-protocol-unix", "-L", "module-null-sink sink_name=callmix",
            "-L", "module-null-sink sink_name=customer"], env=ENV_BASE)
        time.sleep(1)
    mods = sh("pactl list short modules", env=ENV_BASE).stdout
    if "module-loopback" not in mods:
        sh("pactl load-module module-loopback source=customer.monitor sink=callmix latency_msec=20", env=ENV_BASE)
    if "custmic" not in sh("pactl list short sources", env=ENV_BASE).stdout:
        # Chromium hides PulseAudio *monitor* sources from its microphone list: expose the customer sink as a real source
        sh("pactl load-module module-remap-source master=customer.monitor source_name=custmic "
           "source_properties=device.description=CustomerMic", env=ENV_BASE)
    sh("pactl set-default-sink callmix", env=ENV_BASE)
    sh("pactl set-default-source custmic", env=ENV_BASE)


def make_customer_audio(script: dict, langs: list[str], out_dir: pathlib.Path) -> dict:
    """Customer lines with the customer's own voice (offline, before the call: it is the test agent's 'mouth')."""
    import numpy as np
    import soundfile as sf

    from agent.engines import EngineManager
    from agent.voices import VoiceCatalog
    em, cat = EngineManager(), VoiceCatalog()
    files = {}
    for lang in langs:
        v = cat.voice(script[lang]["customer_voice"])
        eng = em.get_tts(v.engine)
        files[lang] = []
        for i, text in enumerate(script[lang]["turns"]):
            syn = eng.synthesize(text, v)
            a = np.asarray(syn.audio, dtype=np.float32)
            a = a * (0.8 / max(float(np.abs(a).max()), 1e-4))
            pad = np.zeros(int(syn.sample_rate * 0.25), np.float32)
            p = out_dir / f"customer_{lang}_{i + 1}.wav"
            sf.write(p, np.concatenate([pad, a, pad]), syn.sample_rate)
            files[lang].append(str(p))
    return files


def start_server(data_dir: str, provider: str) -> subprocess.Popen:
    env = {**os.environ, "SHAON_LOCAL_PREVIEW": "1", "SHAON_DATA_DIR": data_dir, "SHAON_SEED_DEMO": "0", "SHAON_DEVICE": "cpu",
           "SHAON_LLM_PROVIDER": provider, "HF_HUB_OFFLINE": "1", "SHAON_SELF_URL": f"http://127.0.0.1:{PORT}",
           # the same 4 cores also run the headed browser (software WebGL) and the screen recorder
           "SHAON_TORCH_THREADS": os.environ.get("SHAON_TORCH_THREADS", "2"),
           "SHAON_PRELOAD": "lid,stt:en,tts:en,stt:ja,tts:ja,stt:hi,tts:hi,stt:bn,tts:bn,stt:kn,tts:kn"}
    log = open(pathlib.Path(data_dir) / "server.log", "w")
    p = subprocess.Popen([PY, "-m", "uvicorn", "--factory", "api.main:create_app", "--host", "127.0.0.1", "--port", str(PORT),
                          "--log-level", "warning"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            break
        except Exception:
            time.sleep(1)
    for _ in range(300):  # warm every language first: the recordings show the warm system, latency is still real
        try:
            s = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/share/status", timeout=30).read())
            if all(v["state"] in ("ready", "missing", "unavailable") for v in s["languages"].values()):
                break
        except Exception:
            pass
        time.sleep(3)
    return p


def api(method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def set_agent(lang: str, agent_voice: str):
    p = api("GET", "/api/profiles/lotus-bank")
    cfg = p["config"]
    cfg["languages"]["default"] = lang
    cfg["voices"].setdefault("by_language", {})[lang] = agent_voice
    api("PUT", "/api/profiles/lotus-bank", {"config": cfg, "note": f"recording: start in {lang}"})


def probe(mp4: pathlib.Path, run: dict) -> dict:
    j = json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4)]).stdout or "{}")
    v = next((s for s in j.get("streams", []) if s["codec_type"] == "video"), {})
    a = next((s for s in j.get("streams", []) if s["codec_type"] == "audio"), {})

    def vol(t0, t1):
        r = sh(["ffmpeg", "-hide_banner", "-ss", f"{max(t0, 0):.2f}", "-to", f"{t1:.2f}", "-i", str(mp4), "-vn", "-af", "volumedetect", "-f", "null", "-"])
        mv = [ln for ln in r.stderr.splitlines() if "mean_volume" in ln or "max_volume" in ln]
        d = {}
        for ln in mv:
            k, val = ln.split("]")[-1].strip().split(":")
            d[k.strip()] = float(val.replace("dB", "").strip())
        return d
    ev = {}
    for e in run["log"]:
        ev.setdefault(e["ev"], []).append(e)
    rs = ev["record_start"][0]["t"]
    windows = {"customer": [], "agent": []}
    for c0, c1 in zip(ev.get("customer_start", []), ev.get("customer_end", [])):
        windows["customer"].append(vol(c0["t"] - rs + 0.3, c1["t"] - rs - 0.2))
    # agent speech: greeting (call start .. first customer) and after each customer line (until the next customer line)
    starts = [ev["call_start"][0]["t"]] + [c["t"] for c in ev.get("customer_end", [])]
    ends = [c["t"] for c in ev.get("customer_start", [])] + [ev["call_end"][0]["t"]]
    for s0, s1 in zip(starts, ends):
        windows["agent"].append(vol(s0 - rs, s1 - rs))
    return {"duration_s": round(float(j.get("format", {}).get("duration", 0)), 2), "width": v.get("width"), "height": v.get("height"),
            "video_codec": v.get("codec_name"), "audio_codec": a.get("codec_name"), "audio_channels": a.get("channels"),
            "audio_rate": a.get("sample_rate"), "whole": vol(0, 9999), "windows": windows}


def main() -> int:
    langs = sys.argv[1:] or ["en", "hi", "bn", "kn", "ja"]
    script = json.loads((pathlib.Path(__file__).parent / "script.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    ensure_display_and_audio()
    wav_dir = pathlib.Path(tempfile.mkdtemp(prefix="shaon-customer-"))
    files = make_customer_audio(script, langs, wav_dir)
    provider = os.environ.get("RECORD_PROVIDER", "scripted")
    results = []
    for lang in langs:
        data_dir = tempfile.mkdtemp(prefix=f"shaon-rec-{lang}-")
        srv = start_server(data_dir, provider)
        try:
            set_agent(lang, script[lang]["agent_voice"])
            mp4 = OUT / f"shaon-conversation-{lang}.mp4"
            rj = OUT / f"run-{lang}.json"
            r = sh(["node", "scripts/conversation_record.mjs", f"http://127.0.0.1:{PORT}", lang, str(mp4), str(rj), *files[lang]],
                   cwd=ROOT / "web", env=ENV_BASE, timeout=600)
            if r.returncode != 0 or not rj.exists():
                print(f"recorder failed ({r.returncode}):", r.stdout[-1500:], r.stderr[-3000:])
                continue
            run = json.loads(rj.read_text())
            run["probe"] = probe(mp4, run)
            run["customer_voice"], run["agent_voice"] = script[lang]["customer_voice"], script[lang]["agent_voice"]
            run["customer_lines"] = script[lang]["turns"]
            run["provider"] = provider
            rj.write_text(json.dumps(run, ensure_ascii=False, indent=1))
            results.append(run)
            print(lang, json.dumps({k: run["probe"][k] for k in ("duration_s", "width", "height", "audio_codec")}), flush=True)
        finally:
            srv.terminate()
            srv.wait(timeout=30)
            shutil.copy(pathlib.Path(data_dir) / "server.log", OUT / f"server-{lang}.log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
