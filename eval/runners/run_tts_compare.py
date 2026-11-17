"""Compare the CPU-usable TTS engines per language with MEASUREMENTS only (no invented naturalness scores).

For each (language, voice): model load time, first (cold) and warm generation time, audio duration, real-time factor,
peak / clipping / silence, and a round-trip intelligibility proxy: the audio is transcribed by the STT a call would use
for that language and compared with the input text (character error rate). A low round-trip CER means a machine could
understand the voice; it is NOT a naturalness rating (needs native listeners).

  python -m eval.runners.run_tts_compare            # writes eval/out/tts_compare.json and eval/out/tts_samples/*.wav

Indic Parler-TTS is listed as PENDING when its gated weights are not available (HF token + accepted terms).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import unicodedata

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SHAON_DEVICE", "cpu")

SENT = {  # short support-desk lines, native script, numbers as words (as the agent's prompt requires)
    "en": ["Hello, thank you for calling Lotus Bay Bank.", "Our branch opens at ten in the morning on Saturday."],
    "ja": ["お電話ありがとうございます。", "土曜日は午前十時に開店いたします。"],
    "hi": ["नमस्ते, लोटस बे बैंक में कॉल करने के लिए धन्यवाद।", "शनिवार को हमारी शाखा सुबह दस बजे खुलती है।"],
    "bn": ["নমস্কার, লোটাস বে ব্যাংকে ফোন করার জন্য ধন্যবাদ।", "শনিবার আমাদের শাখা সকাল দশটায় খোলে।"],
    "kn": ["ನಮಸ್ಕಾರ, ಲೋಟಸ್ ಬೇ ಬ್ಯಾಂಕ್‌ಗೆ ಕರೆ ಮಾಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು.", "ಶನಿವಾರ ನಮ್ಮ ಶಾಖೆ ಬೆಳಿಗ್ಗೆ ಹತ್ತು ಗಂಟೆಗೆ ತೆರೆಯುತ್ತದೆ."],
}
CANDIDATES = {
    "en": ["kokoro_en_heart", "kokoro_en_michael", "mithi_en_ahana"],
    "ja": ["kokoro_ja_alpha", "kokoro_ja_kumo"],
    "hi": ["kokoro_hi_alpha", "mithi_hi_ahana", "mithi_hi_nakul", "mms_hi"],
    "bn": ["mithi_bn_ahana", "mithi_bn_nakul", "mms_bn"],
    "kn": ["mithi_kn_ahana", "mithi_kn_nakul", "mms_kn"],
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    return "".join(ch for ch in s if ch.isalnum() or ch.isspace()).split().__str__()


def cer(ref: str, hyp: str) -> float:
    a = "".join(ch for ch in unicodedata.normalize("NFC", ref).lower() if ch.isalnum())
    b = "".join(ch for ch in unicodedata.normalize("NFC", hyp).lower() if ch.isalnum())
    if not a:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


def main() -> int:
    from scipy.signal import resample_poly

    from agent.engines import EngineManager
    from agent.voices import VoiceCatalog
    em, cat = EngineManager(), VoiceCatalog()
    out_dir = ROOT / "eval" / "out" / "tts_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, load_s = [], {}
    langs = sys.argv[1:] or list(SENT)
    for lang in langs:
        stt_name, stt_opts, _ = em.stt_route(lang)
        stt = em.get_stt(stt_name, stt_opts)
        for vid in CANDIDATES[lang]:
            v = cat.voice(vid)
            row = {"lang": lang, "voice": vid, "engine": v.engine, "license": v.license, "stt": stt_name}
            try:
                t = time.perf_counter()
                eng = em.get_tts(v.engine)
                load_s.setdefault(v.engine, round(time.perf_counter() - t, 2))
                gens, durs, cers, peaks, clips, sil, hyps = [], [], [], [], [], [], []
                cold = None
                for k, text in enumerate(SENT[lang]):
                    t = time.perf_counter()
                    syn = eng.synthesize(text, v)
                    g = time.perf_counter() - t
                    if k == 0:
                        cold = round(g, 2)
                        t = time.perf_counter(); syn = eng.synthesize(text, v); g = time.perf_counter() - t  # warm
                    a = np.asarray(syn.audio, dtype=np.float32).reshape(-1)
                    d = len(a) / syn.sample_rate
                    gens.append(g); durs.append(d)
                    peaks.append(float(np.abs(a).max())); clips.append(float((np.abs(a) >= 0.999).mean() * 100))
                    env = np.abs(a)
                    sil.append(float((env < 0.01 * max(env.max(), 1e-6) * 10).mean() * 100))
                    import soundfile as sf
                    sf.write(out_dir / f"{vid}_{k}.wav", a, syn.sample_rate)
                    hyp = stt.transcribe(resample_poly(a, 16000, syn.sample_rate).astype(np.float32), lang).text
                    hyps.append(hyp); cers.append(cer(text, hyp))
                row.update(ok=True, load_s=load_s.get(v.engine), cold_gen_s=cold, warm_gen_s=round(float(np.mean(gens)), 2),
                           audio_s=round(float(np.mean(durs)), 2), rtf=round(float(np.sum(gens) / np.sum(durs)), 3),
                           peak=round(max(peaks), 3), clipped_pct=round(max(clips), 3), quiet_pct=round(float(np.mean(sil)), 1),
                           roundtrip_cer=round(float(np.mean(cers)), 3), heard=hyps)
            except Exception as e:
                row.update(ok=False, error=f"{type(e).__name__}: {e}"[:200])
            rows.append(row)
            print(json.dumps({k: row.get(k) for k in ("lang", "voice", "ok", "cold_gen_s", "warm_gen_s", "audio_s", "rtf", "peak",
                                                       "clipped_pct", "roundtrip_cer", "error")}, ensure_ascii=False), flush=True)
    rows.append({"lang": "hi/bn/kn", "voice": "indic-parler (any)", "engine": "indic-parler", "ok": False,
                 "pending": "gated weights (ai4bharat/indic-parler-tts) need an HF token with accepted terms; not run here"})
    from eval.common import save
    save("tts_compare", {"kind": "tts_compare", "note": "CPU, 4 threads. Round-trip CER = recognition proxy, not naturalness.",
                         "engine_load_s": load_s, "rows": rows})
    return 0


if __name__ == "__main__":
    sys.exit(main())
