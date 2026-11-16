"""Build eval/results.md from eval/out/*.json and eval/ratings/*.csv.

Anything not measured yet is printed as PENDING with the command to run.
Synthetic-audio runs (TTS fed into STT) are listed as pipeline checks, never as WER.

  python -m eval.make_report
"""
from __future__ import annotations

import csv
import json
import statistics

from eval.common import EVAL, OUT

LANGS = ["en", "ja", "hi", "bn", "kn"]
RATINGS = EVAL / "ratings"


def fmt(x, pct=False):
    if x is None:
        return "-"
    if pct:
        return f"{x*100:.0f}%"
    return f"{x:.0f}" if isinstance(x, float) and x > 10 else str(x)


def load_all() -> list[dict]:
    if not OUT.exists():
        return []
    out = []
    for p in sorted(OUT.glob("*.json")):
        if p.name.endswith("_manifest.json"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        d["_file"] = p.name
        out.append(d)
    return out


def load_ratings() -> dict[tuple[str, str], list[int]]:
    """(type, item_id) -> scores. Files: eval/ratings/*.csv from rater.html."""
    agg: dict[tuple[str, str], list[int]] = {}
    for p in sorted(RATINGS.glob("*.csv")) if RATINGS.exists() else []:
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("score"):
                    agg.setdefault((r["type"], r["item_id"]), []).append(int(r["score"]))
    return agg


def section_hw(lines, data):
    hw = next((d for d in data if d.get("kind") == "hardware"), None)
    lines.append("## Hardware\n")
    if not hw:
        lines.append("PENDING: `python scripts/check_hardware.py`\n")
        return
    g = hw.get("gpus") or []
    gpu = ", ".join(f"{x['name']} {x['vram_mb']} MB" for x in g) or "no NVIDIA GPU"
    lines.append(f"- Host `{hw['host']}` ({hw['os']}), CPU {hw['cpu_count']} cores, RAM {hw['ram_gb']} GB, GPU: {gpu}")
    lines.append(f"- Decision: **{hw['decision']}**. {hw['reason']}\n")


def section_stt(lines, data):
    lines.append("## STT (word / character error rate, oracle language)\n")
    runs = [d for d in data if d.get("kind") == "stt" and not d.get("synthetic")]
    synth = [d for d in data if d.get("kind") == "stt" and d.get("synthetic")]
    if not runs:
        lines.append("PENDING: record lines (eval/tools/recorder.html), then `python -m eval.runners.run_stt --engine ...` (see eval/README.md)\n")
    else:
        lines.append("| engine | lang | n | WER | CER | WER excl. number lines | p50 ms | p90 ms | RTF | load s | peak GPU MB |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for d in runs:
            name = f"{d['engine']} {json.dumps(d['options'])}"
            for lang in LANGS:
                v = d["per_lang"].get(lang)
                if v:
                    lines.append(f"| {name} | {lang} | {v['n']} | {fmt(v.get('wer'), True)} | {fmt(v.get('cer'), True)} | "
                                 f"{fmt(v.get('no_numbers', {}).get('wer' if lang != 'ja' else 'cer'), True)} | "
                                 f"{fmt(v['latency_p50_ms'])} | {fmt(v['latency_p90_ms'])} | {v['rtf_mean']} | {d['load_s']} | {fmt(d['peak_gpu_mb'])} |")
        lines.append("")
    if synth:
        lines.append("Pipeline checks on synthetic (TTS) audio, NOT accuracy results: "
                     + ", ".join(d["_file"] for d in synth) + "\n")


def section_lid(lines, data):
    lines.append("## Language ID\n")
    runs = [d for d in data if d.get("kind") == "lid" and not d.get("synthetic")]
    if not runs:
        lines.append("PENDING: `python -m eval.runners.run_lid --model large-v3`\n")
        return
    for d in runs:
        pl = ", ".join(f"{k} {fmt(v, True)}" for k, v in d["raw_top1_per_lang"].items() if v is not None)
        lines.append(f"- {d['model']}: raw top-1 mono {fmt(d['raw_top1_mono'], True)}, mixed {fmt(d['raw_top1_mixed'], True)} ({pl}); detect p50 {fmt(d['detect_latency_p50_ms'])} ms")
        b = d.get("recommended")
        if b:
            lines.append(f"- Recommended routing: threshold {b['threshold']}, prev_bias {b['prev_bias']}, script check {b['script_check']} -> stay {fmt(b['stay_acc'], True)}, switch {fmt(b['switch_acc'], True)}. Copy into agent/engines.json `lid`.")
    lines.append("")


def section_switch(lines, data):
    lines.append("## Language switching (PLAN M3 rule: 3 consecutive switch directions per pair)\n")
    real = [d for d in data if d.get("kind") == "switch" and not d.get("synthetic")]
    synth = [d for d in data if d.get("kind") == "switch" and d.get("synthetic")]
    if not real:
        lines.append("PENDING: native recordings, then `python -m eval.runners.run_switch`\n")
    for d in real:
        lines.append(f"- languages {', '.join(d['langs'])}: pass rate {fmt(d['pass_rate'], True)}; "
                     + ", ".join(f"{x['pair']} {'PASS' if x['pass'] else 'FAIL'}" for x in d["pairs"]))
    for d in synth:
        lines.append(f"- Synthetic pipeline check (Kokoro audio, not accuracy): {', '.join(d['langs'])}: "
                     + ", ".join(f"{x['pair']} {'PASS' if x['pass'] else 'FAIL'}" for x in d["pairs"]))
    lines.append("")


def section_tts(lines, data, ratings):
    lines.append("## TTS\n")
    d = next((d for d in data if d.get("kind") == "tts"), None)
    if not d:
        lines.append("PENDING: `python -m eval.runners.run_tts --roundtrip`, then native-speaker ratings (eval/tools/rater.html)\n")
        return
    lines.append("| voice | lang | engine | license | first audio p50 ms | p90 ms | RTF | peak GPU MB | round-trip CER | naturalness 1-5 (n) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for vid, v in sorted(d["voices"].items(), key=lambda kv: (LANGS.index(kv[1]["lang"]), kv[0])):
        sc = [s for (t, i), ss in ratings.items() if t == "tts" and i.startswith(vid + "/") for s in ss]
        mos = f"{statistics.mean(sc):.2f} ({len(sc)})" if sc else "PENDING"
        lic = v["license"] + (" DEMO ONLY" if v["demo_only"] else "")
        lines.append(f"| {vid} | {v['lang']} | {v['engine']} | {lic} | {fmt(v['first_audio_p50_ms'])} | {fmt(v['first_audio_p90_ms'])} | "
                     f"{v['rtf_mean']} | {fmt(v.get('peak_gpu_mb'))} | {fmt(v.get('roundtrip_cer'), True)} | {mos} |")
    lines.append("\nNo engine streams: first audio = full sentence generation time. Round-trip CER = TTS output transcribed by the configured STT (intelligibility proxy, not naturalness).\n")


def section_llm(lines, data, ratings):
    lines.append("## Claude replies\n")
    runs = [d for d in data if d.get("kind") == "llm"]
    if not runs:
        lines.append("PENDING: `python -m eval.runners.run_llm` (quick set, $0.50 cap)\n")
        return
    lines.append("| run | lang | n | language ok | native script | no digits | <=2 sentences | format ok | TTFT p50 ms | p90 ms | refusals | native rating 1-5 (n) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for d in runs:
        tag = d["_file"].removesuffix(".json")
        for lang in LANGS:
            v = d["per_lang"].get(lang)
            if not v:
                continue
            sc = [s for (t, i), ss in ratings.items() if t == "llm" and i.startswith(tag + "/" + lang) for s in ss]
            r = f"{statistics.mean(sc):.2f} ({len(sc)})" if sc else "PENDING"
            lines.append(f"| {tag} | {lang} | {v['n']} | {fmt(v['lang_ok'], True)} | {fmt(v['native_ok'], True)} | {fmt(v['no_digits'], True)} | "
                         f"{fmt(v['short_ok'], True)} | {fmt(v['format_ok'], True)} | {fmt(v['ttft_p50_ms'])} | {fmt(v['ttft_p90_ms'])} | {v['refusals']} | {r} |")
        sw = d["switch"]
        lines.append(f"\n{tag}: mixed lines language ok {fmt(d['mixed']['lang_ok'], True)}; switch test {fmt(sw['lang_ok'], True)} of {sw['n']} pairs"
                     + (f" (failed: {', '.join(sw['failures'])})" if sw["failures"] else "") + f"; spent ${d['spent_usd']}\n")


def section_retrieval(lines, data):
    lines.append("## Cross-lingual retrieval (BGE-M3, English chunks)\n")
    d = next((d for d in data if d.get("kind") == "retrieval"), None)
    if not d:
        lines.append("PENDING: `python -m eval.runners.run_retrieval`\n")
        return
    lines.append("| lang | n | hit@1 | hit@3 |\n|---|---|---|---|")
    for lang in LANGS:
        v = d["per_lang"].get(lang)
        if v:
            lines.append(f"| {lang} | {v['n']} | {fmt(v['hit1'], True)} | {fmt(v['hit3'], True)} |")
    lines.append(f"\nMixed lines hit@1 {fmt(d['mixed']['hit1'], True)} (n={d['mixed']['n']}). Query embed {d['query_ms']} ms each, load {d['load_s']} s, peak GPU {fmt(d['peak_gpu_mb'])} MB.\n")


def section_kb(lines, data):
    lines.append("## Cross-lingual retrieval through the ingestion pipeline (M4: crawl -> clean -> chunk -> embed -> Chroma)\n")
    d = next((d for d in data if d.get("kind") == "kb_retrieval"), None)
    if not d:
        lines.append("PENDING: `SHAON_EMBEDDER=bge-m3 python -m eval.runners.run_kb`\n")
        return
    lines.append(f"Embedder: {d['embedder']}. Queries = test lines whose topic has an answer page on the two fake sites.\n")
    lines.append("| lang | n | hit@1 | hit@3 |\n|---|---|---|---|")
    for lang in LANGS:
        v = d["per_lang"].get(lang)
        if v:
            lines.append(f"| {lang} | {v['n']} | {fmt(v['hit1'], True)} | {fmt(v['hit3'], True)} |")
    lines.append(f"\nMixed lines hit@1 {fmt(d['mixed']['hit1'], True)} (n={d['mixed']['n']}).\n")


def section_redteam(lines, data):
    lines.append("## Guardrails red-team (50 attacks: 10 per preset, jailbreaks in all 5 languages)\n")
    runs = [d for d in data if d.get("kind") == "redteam"]
    if not any(d["mode"] == "claude" for d in runs):
        lines.append("Claude run PENDING (needs the API key): `python -m eval.runners.run_redteam --real --max-usd 0.30`\n")
    for d in runs:
        s = d["summary"]
        lines.append(f"- {d['mode']}: overall {fmt(s['overall'], True)}; attacks expected at the local layer {fmt(s['local_expected'], True)}; "
                     f"attacks needing the model check {fmt(s['model_expected'], True)}")
        lines.append("  per preset: " + ", ".join(f"{k} {fmt(v, True)}" for k, v in s["per_preset"].items())
                     + "; per language: " + ", ".join(f"{k} {fmt(v, True)}" for k, v in s["per_lang"].items()))
        fails = [r["id"] for r in d["rows"] if not r["pass"]]
        if fails:
            lines.append(f"  not stopped: {', '.join(fails)}")
    lines.append("")


def section_fleurs(lines, data):
    lines.append("## Real-audio STT on FLEURS (CPU)\n")
    lines.append("google/fleurs test split (CC-BY-4.0, Conneau et al. 2022), fixed seed, one recording per sentence. "
                 "**Caveat:** clean read Wikipedia-style speech, not phone calls - numbers are optimistic for live calls; "
                 "Whisper small/base on CPU are stand-ins for the GPU engines. Text normalized per language (NFC, lowercase, "
                 "punctuation/danda removed, native digits -> ASCII); CER for Japanese. Oracle language given to the recognizer.\n")
    runs = sorted([d for d in data if d.get("kind") == "fleurs_stt"], key=lambda d: d["engine"])
    if not runs:
        lines.append("PENDING: `python -m eval.runners.run_fleurs --stt whisper-small whisper-base mms indicconformer --lid`\n")
        return
    lines.append("| engine (weights) | lang | n | WER | CER | WER, refs without digits (n) | WER / CER Indic-folded* | median ms | worst-10% ms (p90) | RTF median |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for d in runs:
        if d.get("status") != "measured":
            lines.append(f"| {d['engine']} ({d['repo']}) | hi/bn/kn | - | PENDING | | | | | |")
            continue
        size = f"{d['weights_bytes'] / 1e6:.0f} MB" if d.get("weights_bytes") else "?"
        for lang in LANGS:
            v = d["per_lang"].get(lang)
            if v:
                nd = v["no_digit_refs"]
                lines.append(f"| {d['engine']} ({d['repo']}, {size}, {d['format']}) | {lang} | {v['n']} | {fmt(v.get('wer'), True)} | "
                             f"{fmt(v.get('cer'), True)} | {fmt(nd.get('wer') if lang != 'ja' else nd.get('cer'), True)} ({nd['n']}) | "
                             f"{fmt(v['latency_median_ms'])} | {fmt(v['latency_p90_ms'])} | {v['rtf_median']} |")
    lines.append("\n*Indic-folded = same transcripts rescored after folding nukta forms (ज़/ज, ড়/ড) and chandrabindu/anusvara: "
                 "spelling variants, not recognition errors. Secondary metric; the strict WER/CER is primary.")
    pend = [d for d in runs if d.get("status") != "measured"]
    for d in pend:
        lines.append(f"\n{d['engine']}: PENDING - {d.get('reason', '')[:160]}")
    lines.append("")
    lid = next((d for d in data if d.get("kind") == "fleurs_lid"), None)
    lines.append("### Language ID on the same clips (the app's real path: Whisper small LID + routing, call starting in English)\n")
    if not lid:
        lines.append("PENDING\n")
        return
    lines.append(f"Overall raw top-1 {fmt(lid['overall_raw_top1'], True)}; app decision {fmt(lid['overall_app'], True)}; "
                 f"median LID time {fmt(lid['lid_ms_median'])} ms.\n")
    lines.append("| true \\ detected | " + " | ".join(LANGS) + " | raw top-1 | app decision | median confidence |")
    lines.append("|---|" + "---|" * (len(LANGS) + 3))
    for tl in LANGS:
        row = lid["confusion_raw"][tl]
        v = lid["per_lang"][tl]
        lines.append(f"| {tl} | " + " | ".join(str(row[p]) for p in LANGS) + f" | {fmt(v['raw_top1'], True)} | {fmt(v['app_from_en'], True)} | {v['median_conf']} |")
    b = lid.get("recommended")
    if b:
        lines.append(f"\nThreshold sweep (stay = previous turn in the same language, switch = previous turn in another language): "
                     f"best threshold {b['threshold']}, prev_bias {b['prev_bias']}, script check {b['script_check']} -> stay {fmt(b['stay_acc'], True)}, "
                     f"switch {fmt(b['switch_acc'], True)}. **Proposed values are CPU / read-speech estimates: re-measure on the demo PC.**")
    lines.append("")


def section_tts_cpu(lines, data):
    d = next((d for d in data if d.get("kind") == "tts_cpu"), None)
    lines.append("## CPU speaking engines for hi / bn / kn (demo mode)\n")
    if not d:
        lines.append("PENDING: `python -m eval.runners.run_tts_cpu`\n")
        return
    lines.append("MMS voices are robotic pipeline-testing voices (CC-BY-NC, DEMO ONLY). Round-trip CER = TTS output transcribed back "
                 "by the best measured STT: an intelligibility PROXY, not naturalness. Reply lines machine-written (native review pending).\n")
    lines.append("| voice | lang | engine | license | first audio median ms | p90 ms | RTF median | round-trip CER (proxy) | via |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for vid, v in d["voices"].items():
        lines.append(f"| {vid} | {v['lang']} | {v['engine']} | {v['license']} | {fmt(v['first_audio_median_ms'])} | {fmt(v['first_audio_p90_ms'])} | "
                     f"{v['rtf_median']} | {fmt(v.get('roundtrip_cer'), True)} | {v.get('roundtrip_stt', '')} |")
    lines.append("")


def section_indic_e2e(lines, data):
    d = next((d for d in data if d.get("kind") == "indic_e2e"), None)
    lines.append("## Live-call E2E with real speech: hi / bn / kn and switches (CPU, scripted fake LLM)\n")
    if not d:
        lines.append("PENDING: `python tests/e2e/run_indic_e2e.py`\n")
        return
    lines.append(f"Pass rate {fmt(d['pass_rate'], True)} ({sum(c['pass'] for c in d['cases'])}/{len(d['cases'])} calls). {d['note']}\n")
    lines.append("| call | turn | detected | STT engine | reply lang | TTS voice | first audio ms | result |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for c in d["cases"]:
        for t in c["turns"]:
            bad = [k for k, ok in t["checks"].items() if not ok]
            lines.append(f"| {c['case']} | {t['want']} | {t['detected']} | {t['stt_engine']} | {t['reply_lang']} | {t['tts_voice']} | "
                         f"{fmt(t['first_audio_ms'])} | {'PASS' if t['pass'] else 'FAIL: ' + ', '.join(bad)} |")
    lines.append("")


def main():
    data = load_all()
    ratings = load_ratings()
    lines = ["# M0 results\n",
             "Generated by `python -m eval.make_report` from eval/out/ and eval/ratings/. Do not edit tables by hand; "
             "add conclusions under Decisions. Every number here was measured; missing ones say PENDING.\n"]
    section_hw(lines, data)
    section_stt(lines, data)
    section_lid(lines, data)
    section_fleurs(lines, data)
    section_switch(lines, data)
    section_tts(lines, data, ratings)
    section_tts_cpu(lines, data)
    section_indic_e2e(lines, data)
    section_llm(lines, data, ratings)
    section_retrieval(lines, data)
    section_kb(lines, data)
    section_redteam(lines, data)
    dec = EVAL / "decisions.md"
    lines.append("## Decisions\n")
    lines.append(dec.read_text(encoding="utf-8") if dec.exists() else "PENDING: engines are locked after native-speaker ratings.\n")
    (EVAL / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {EVAL / 'results.md'}")


if __name__ == "__main__":
    main()
