#!/usr/bin/env python3
"""Fast self-test after installing (scripts/install.ps1 runs it): per language, ONE text-to-speech with the voice a call
would use, then ONE speech-to-text of that audio with the engine a call would route to. No Claude call, no network:
it runs with HF_HUB_OFFLINE=1, which also proves every model is already on disk.

  python scripts/selftest.py              # all five languages
  python scripts/selftest.py --lang hi    # one language

Prints a plain table; on failure a one-line reason and what to do (no stack trace). Exit 0 = all passed.
MMS voices/engines used for bn/kn (and as hi fallback) are CC-BY-NC: DEMO ONLY.
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import pathlib
import sys
import time
import warnings
from contextlib import redirect_stderr, redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

# short native-script greetings (no digits: TTS reads words)
TEXT = {
    "en": "Hello, thank you for calling. How can I help you today?",
    "ja": "お電話ありがとうございます。本日はどのようなご用件でしょうか。",
    "hi": "नमस्ते, कॉल करने के लिए धन्यवाद। मैं आपकी कैसे मदद कर सकती हूँ?",
    "bn": "নমস্কার, ফোন করার জন্য ধন্যবাদ। আমি কীভাবে সাহায্য করতে পারি?",
    "kn": "ನಮಸ್ಕಾರ, ಕರೆ ಮಾಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
}
HINT = {
    "kokoro": "Kokoro voice failed: run the installer again (it repairs Python packages and models).",
    "mms-tts": "MMS voice failed: run the installer again (it re-downloads missing models).",
    "faster-whisper": "Whisper failed: run the installer again; if it persists, delete the folder models--Systran--faster-whisper-small in the Hugging Face cache.",
    "mms": "MMS speech-to-text failed: run the installer again (it re-downloads missing models).",
}


def quiet(fn, *a, **kw):
    """Run fn without library chatter on stdout/stderr (we print our own table)."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return fn(*a, **kw)


def plain(e: Exception) -> str:
    msg = f"{type(e).__name__}: {e}".splitlines()[0]
    if "offline" in msg.lower() or "LocalEntryNotFound" in msg or "outgoing traffic has been disabled" in msg:
        return "a model file is missing on disk (offline check)"
    return msg[:160]


def voice_for(engines, cat, lang):
    """Same order as a call: default voice, then the CPU fallbacks; first one whose engine is installed."""
    from agent.engines import installed
    ids = [engines.cfg["default_voices"].get(lang)]
    fb = engines.cfg.get("cpu_fallback_voices", {}).get(lang) or []
    ids += [fb] if isinstance(fb, str) else fb
    tried = []
    for vid in [i for i in ids if i]:
        v = cat.voice(vid)
        if v and v.engine in _ENGINE_KEYS and installed(v.engine):
            return v, tried
        tried.append(vid)
    return None, tried


_ENGINE_KEYS = {"kokoro", "mms-tts", "indic-parler", "omnivoice"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", action="append", choices=list(TEXT))
    a = ap.parse_args()
    langs = a.lang or list(TEXT)
    import numpy as np
    from scipy.signal import resample_poly

    from agent.engines import EngineManager
    from agent.lang.script import dominant_language
    from agent.voices import VoiceCatalog

    engines = EngineManager()
    cat = VoiceCatalog()
    print(f"ShaOn self-test ({'GPU' if engines.cuda else 'CPU'} mode, offline, no Claude call)")
    print(f"  {'lang':<5}{'voice':<18}{'tts s':>7}  {'stt engine':<16}{'stt s':>7}  result")
    failures = []
    for lang in langs:
        v, _ = voice_for(engines, cat, lang)
        if v is None:
            failures.append((lang, "no voice engine installed", HINT["kokoro"]))
            print(f"  {lang:<5}{'-':<18}{'':>7}  {'':<16}{'':>7}  FAIL  no voice engine installed")
            continue
        t0 = time.time()
        try:
            syn = quiet(lambda: engines.get_tts(v.engine).synthesize(TEXT[lang], v))
            audio = np.asarray(syn.audio, dtype=np.float32)
            if audio.size < syn.sample_rate * 0.3 or float(np.abs(audio).max()) < 1e-3:
                raise RuntimeError("the voice produced silence")
        except Exception as e:
            failures.append((lang, f"voice {v.id}: {plain(e)}", HINT.get(v.engine, HINT["kokoro"])))
            print(f"  {lang:<5}{v.id:<18}{time.time() - t0:>7.1f}  {'':<16}{'':>7}  FAIL  voice: {plain(e)}")
            continue
        tts_s = time.time() - t0
        pcm16k = resample_poly(audio, 16000, syn.sample_rate).astype(np.float32)
        name, opts, _ = engines.stt_route(lang)
        t1 = time.time()
        try:
            stt = quiet(engines.get_stt, name, opts)
            text = quiet(stt.transcribe, pcm16k, lang).text.strip()
        except Exception as e:
            failures.append((lang, f"speech-to-text {name}: {plain(e)}", HINT.get(name, HINT["mms"])))
            print(f"  {lang:<5}{v.id:<18}{tts_s:>7.1f}  {name:<16}{time.time() - t1:>7.1f}  FAIL  speech-to-text: {plain(e)}")
            continue
        stt_s = time.time() - t1
        got, _share = dominant_language(text)
        ok = bool(text) and (got == lang or (lang in ("en",) and got in (None, "en")))
        res = "PASS" if ok else f"FAIL  heard {got or 'nothing'}"
        print(f"  {lang:<5}{v.id:<18}{tts_s:>7.1f}  {name:<16}{stt_s:>7.1f}  {res}   \"{text[:40]}\"")
        if not ok:
            failures.append((lang, f"speech-to-text heard {text[:40]!r}", "Run the installer again; if it repeats, report the line above."))
    print()
    if failures:
        print("SELF-TEST FAILED for: " + ", ".join(f[0] for f in failures))
        for lang, why, fix in failures:
            print(f"  {lang}: {why}\n      -> {fix}")
        return 1
    print("Self-test passed: every language can speak and listen on this PC.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:  # never a stack trace for the user
        print(f"SELF-TEST FAILED: {plain(e)}\n  -> Run the installer again; it repairs missing packages and models.")
        sys.exit(1)
