"""M3 pass rule (PLAN.md): 3 consecutive switch directions on the test lines per language pair.

For each ordered pair (A, B): feed lines A, B, A, B through the REAL routing (CallSession.transcribe_turn
with the configured engines), starting from previous language A. Pass = all 4 turns land on the right language.

  python -m eval.runners.run_switch                       # native recordings in eval/audio/
  python -m eval.runners.run_switch --audio-dir eval/out/tts/kokoro_en_heart --audio-dir eval/out/tts/kokoro_ja_alpha --synthetic
"""
from __future__ import annotations

import argparse
import itertools
import pathlib

from agent.audio import load_audio
from agent.brain import CallContext
from agent.engines import EngineManager
from agent.pipeline.session import CallSession, Hooks
from agent.presets import preset
from agent.voices import VoiceCatalog
from eval.common import AUDIO, audio_for, load_lines, save


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-dir", action="append", default=None)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--langs", nargs="*")
    a = ap.parse_args(argv)
    dirs = [pathlib.Path(d) for d in (a.audio_dir or [str(AUDIO)])]

    by_lang: dict[str, list] = {}
    for line in load_lines(a.langs, include_mixed=False):
        p = next((x for x in (audio_for(line["id"], d) for d in dirs) if x), None)
        if p:
            by_lang.setdefault(line["lang"], []).append((line, p))
    langs = sorted(l for l, v in by_lang.items() if len(v) >= 2)
    if len(langs) < 2:
        print("Need recordings for at least two languages (2+ lines each).")
        return 1
    engines = EngineManager()
    results = []
    for la, lb in itertools.permutations(langs, 2):
        prof = preset("bank_support")
        prof["languages"]["enabled"] = langs
        prof["languages"]["default"] = la
        s = CallSession(ctx=CallContext(call_id="switch", profile=prof), engines=engines, voices=VoiceCatalog(),
                        hooks=Hooks(provider=lambda: None))
        seq = [by_lang[la][0], by_lang[lb][0], by_lang[la][1], by_lang[lb][1]]
        turns = []
        for line, path in seq:
            info = s.transcribe_turn(load_audio(str(path)))
            turns.append({"id": line["id"], "want": line["lang"], "got": info["lang"], "reason": info["reason"],
                          "stt_ms": info["stt_ms"], "text": info["text"]})
        ok = all(t["want"] == t["got"] for t in turns)
        results.append({"pair": f"{la}->{lb}", "pass": ok, "turns": turns})
        print(f"{la}->{lb}: {'PASS' if ok else 'FAIL'}", [(t['want'], t['got'], t['reason']) for t in turns])
    p = save(f"switch{'_synthetic' if a.synthetic else ''}", {"kind": "switch", "synthetic": a.synthetic, "langs": langs,
             "pass_rate": round(sum(r["pass"] for r in results) / len(results), 3), "pairs": results})
    print(f"saved {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
