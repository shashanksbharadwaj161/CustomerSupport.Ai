#!/usr/bin/env python3
"""Download every model the CPU demo mode uses (scripts/install.ps1 runs this). Free, from Hugging Face + UniDic.

  python scripts/fetch_models.py            # show sizes, then download what is missing (resumes partial files)
  python scripts/fetch_models.py --check    # only report; exit 0 if everything is present, 1 if not
  python scripts/fetch_models.py --optional # also the gated IndicConformer (needs HF_TOKEN in the environment)

Already-downloaded files are skipped without any network call, so later runs take seconds.
Interrupted downloads resume from where they stopped (Hugging Face keeps .incomplete files); each file is retried.
Licences: Whisper MIT, Kokoro Apache-2.0, BGE-M3 MIT, Silero MIT (bundled in pipecat, nothing to download);
MMS (facebook/mms-*) CC-BY-NC-4.0 = DEMO ONLY, never a product voice/engine. Weights never go into git.
The HF token is read from the environment only (never a command-line argument, never printed).
Exit codes: 0 ok, 1 missing (--check), 2 download failed, 3 not enough disk space.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # Windows without developer mode: copies, fine
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

GB = 1024 ** 3
KOKORO_VOICES = ["af_heart", "af_bella", "am_michael", "bm_george", "jf_alpha", "jm_kumo", "jf_nezumi", "hf_alpha", "hm_omega"]
TOKENIZER = ["config.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.json"]

# (repo, files, approx bytes when the size cannot be fetched, what it is for)
MANIFEST = [
    ("Systran/faster-whisper-small", ["model.bin", "config.json", "tokenizer.json", "vocabulary.txt"], 0.49 * GB,
     "Whisper small: English + Japanese speech-to-text, language ID (MIT)"),
    ("facebook/mms-1b-all", ["model.safetensors", "preprocessor_config.json"] + TOKENIZER +
     ["adapter.hin.safetensors", "adapter.ben.safetensors", "adapter.kan.safetensors"], 3.89 * GB,
     "MMS-1B-all: Hindi/Bengali/Kannada speech-to-text (CC-BY-NC, DEMO ONLY)"),
    ("facebook/mms-tts-hin", ["model.safetensors"] + TOKENIZER, 0.15 * GB, "MMS-TTS Hindi fallback voice (CC-BY-NC, DEMO ONLY)"),
    ("facebook/mms-tts-ben", ["model.safetensors"] + TOKENIZER, 0.15 * GB, "MMS-TTS Bengali voice (CC-BY-NC, DEMO ONLY, robotic)"),
    ("facebook/mms-tts-kan", ["model.safetensors"] + TOKENIZER, 0.15 * GB, "MMS-TTS Kannada voice (CC-BY-NC, DEMO ONLY, robotic)"),
    ("hexgrad/Kokoro-82M", ["config.json", "kokoro-v1_0.pth"] + [f"voices/{v}.pt" for v in KOKORO_VOICES], 0.33 * GB,
     "Kokoro: English, Japanese, Hindi voices (Apache-2.0)"),
    ("BAAI/bge-m3", ["pytorch_model.bin", "config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                     "sentencepiece.bpe.model", "modules.json", "sentence_bert_config.json", "config_sentence_transformers.json",
                     "1_Pooling/config.json"], 2.29 * GB, "BGE-M3: website knowledge search across languages (MIT)"),
]
OPTIONAL = [("ai4bharat/indic-conformer-600m-multilingual", None, 2.5 * GB,
             "IndicConformer: better Hindi/Bengali/Kannada speech-to-text (gated: accept terms + HF token)")]
UNIDIC_BYTES = 0.53 * GB  # download size of the UniDic zip (unpacks to ~0.8 GB)


def human(n: float) -> str:
    return f"{n / GB:.2f} GB" if n >= 0.1 * GB else f"{n / 1024 ** 2:.1f} MB"


def cached(repo: str, f: str) -> bool:
    from huggingface_hub import try_to_load_from_cache
    p = try_to_load_from_cache(repo, f)
    return isinstance(p, str) and os.path.exists(p)


def snapshot_cached(repo: str) -> bool:
    from huggingface_hub import scan_cache_dir
    try:
        return any(r.repo_id == repo and r.size_on_disk > 100 * 1024 ** 2 for r in scan_cache_dir().repos)
    except Exception:
        return False


def unidic_ok() -> bool:
    try:
        import unidic
        return os.path.exists(os.path.join(unidic.DICDIR, "mecabrc"))
    except Exception:
        return True  # unidic not installed => Japanese not set up through this package; nothing to fetch


def remote_sizes(repo: str) -> dict[str, int]:
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(repo, files_metadata=True)
        return {s.rfilename: int(s.size or 0) for s in info.siblings or []}
    except Exception:
        return {}


def cache_dir() -> str:
    from huggingface_hub import constants
    return constants.HF_HUB_CACHE


def plan(optional: bool) -> list[dict]:
    items = []
    for repo, files, approx, what in MANIFEST:
        missing = [f for f in files if not cached(repo, f)]
        items.append({"repo": repo, "files": files, "missing": missing, "approx": approx, "what": what, "kind": "files"})
    if optional:
        for repo, _, approx, what in OPTIONAL:
            items.append({"repo": repo, "files": None, "missing": [] if snapshot_cached(repo) else ["*"], "approx": approx,
                          "what": what, "kind": "snapshot"})
    items.append({"repo": "UniDic", "files": None, "missing": [] if unidic_ok() else ["dictionary"], "approx": UNIDIC_BYTES,
                  "what": "UniDic: Japanese dictionary for the Kokoro Japanese voice", "kind": "unidic"})
    return items


def sizes_for(items: list[dict]) -> None:
    for it in items:
        it["total"] = it["approx"]
        it["todo"] = it["approx"] if it["missing"] else 0
        if it["kind"] == "files" and it["missing"]:
            rs = remote_sizes(it["repo"])
            if rs:
                it["total"] = sum(rs.get(f, 0) for f in it["files"])
                it["todo"] = sum(rs.get(f, 0) for f in it["missing"])
                it["sizes"] = rs


def download_file(repo: str, f: str, tries: int = 5) -> None:
    from huggingface_hub import hf_hub_download
    for attempt in range(1, tries + 1):
        try:
            hf_hub_download(repo, f)  # resumes a partial download (.incomplete) automatically
            return
        except KeyboardInterrupt:
            raise
        except Exception as e:
            msg = f"{type(e).__name__}: {e}".splitlines()[0][:200]
            if any(c in msg for c in ("404", "401", "403")) or "NotFound" in type(e).__name__:
                raise RuntimeError(f"{repo}/{f}: {msg}") from None  # not a network hiccup: retrying cannot help
            if attempt == tries:
                raise RuntimeError(f"{repo}/{f}: {msg}") from None
            wait = min(60, 5 * 2 ** (attempt - 1))
            print(f"    download interrupted ({msg}); retry {attempt}/{tries - 1} in {wait} s (resumes, nothing is lost)", flush=True)
            time.sleep(wait)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--optional", action="store_true", help="also the gated IndicConformer (needs HF_TOKEN env)")
    ap.add_argument("--only", action="append", default=[], help="limit to these repos (testing / repair)")
    ap.add_argument("--min-free-gb", type=float, default=2.0, help="keep this much disk free after downloading")
    a = ap.parse_args()
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        print("The Python packages are not installed yet (huggingface_hub missing).")
        return 2
    optional = a.optional and bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    items = plan(optional)
    if a.only:
        items = [it for it in items if it["repo"] in a.only]
    todo = [it for it in items if it["missing"]]
    if not todo:
        print(f"Models: all {len(items)} present (cache: {cache_dir()}). Nothing to download.")
        return 0
    if a.check:
        for it in todo:
            print(f"missing: {it['repo']} ({len(it['missing'])} file(s))")
        return 1
    sizes_for(items)
    total = sum(it["total"] for it in items)
    need = sum(it["todo"] for it in items)
    print(f"Models for CPU demo mode: {human(total)} in total, {human(need)} still to download.")
    print(f"{'':2}{'model':<46}{'size':>10}  status")
    for it in items:
        print(f"  {it['repo']:<46}{human(it['total']):>10}  {'to download' if it['missing'] else 'present'}")
        print(f"      {it['what']}")
    os.makedirs(cache_dir(), exist_ok=True)
    free = shutil.disk_usage(cache_dir()).free
    if free < need + a.min_free_gb * GB:
        print(f"\nNot enough disk space: {human(free)} free on the drive with {cache_dir()}, "
              f"need {human(need)} plus {a.min_free_gb:.0f} GB spare. Free some space and run the installer again.")
        return 3
    failed = []
    step = 0
    nsteps = sum(len(it["missing"]) for it in todo)
    for it in todo:
        try:
            if it["kind"] == "files":
                for f in it["missing"]:
                    step += 1
                    size = it.get("sizes", {}).get(f)
                    print(f"\n[{step}/{nsteps}] {it['repo']}  {f}" + (f"  ({human(size)})" if size else ""), flush=True)
                    download_file(it["repo"], f)
            elif it["kind"] == "snapshot":
                step += 1
                print(f"\n[{step}/{nsteps}] {it['repo']} (optional, gated)", flush=True)
                from huggingface_hub import snapshot_download
                snapshot_download(it["repo"])
            else:
                step += 1
                print(f"\n[{step}/{nsteps}] UniDic Japanese dictionary (~{human(UNIDIC_BYTES)})", flush=True)
                for attempt in range(3):
                    r = subprocess.run([sys.executable, "-m", "unidic", "download"])
                    if r.returncode == 0 and unidic_ok():
                        break
                    print(f"    UniDic download failed; retry {attempt + 1}/2", flush=True)
                    time.sleep(10)
                if not unidic_ok():
                    raise RuntimeError("UniDic download failed")
        except KeyboardInterrupt:
            print("\nStopped. Run the installer again: finished files are kept and partial ones resume.")
            return 2
        except Exception as e:
            msg = str(e)
            if "401" in msg or "403" in msg or "gated" in msg.lower():
                msg += "  (this model is gated: accept its terms on huggingface.co with the account of your token)"
            failed.append((it["repo"], msg))
            print(f"    FAILED: {msg}", flush=True)
    if failed:
        print("\nSome downloads did not finish:")
        for repo, msg in failed:
            print(f"  - {repo}: {msg}")
        print("Check the internet connection and run the installer again: it continues where it stopped.")
        return 2
    print(f"\nAll models downloaded ({human(total)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
