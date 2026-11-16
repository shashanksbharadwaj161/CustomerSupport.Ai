#!/usr/bin/env python3
"""Environment checklist: what is installed, what is missing, and the exact command to fix each item.
Read-only. Prints PASS / MISSING / PENDING lines. Exit code 0 even when items are missing (demo mode still works)."""
from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def mod(name):
    return importlib.util.find_spec(name) is not None


def hf_cached(repo, f="config.json"):
    try:
        from huggingface_hub import try_to_load_from_cache
        return isinstance(try_to_load_from_cache(repo, f), str)
    except Exception:
        return False


def line(state, what, fix=""):
    print(f"[{state:<7}] {what}" + (f"\n          -> {fix}" if fix and state != "PASS" else ""))


def main():
    print(f"ShaOn doctor  (python {sys.version.split()[0]}, {sys.platform})\n")
    v = sys.version_info
    line("PASS" if (3, 10) <= v[:2] <= (3, 12) else "MISSING", "Python 3.10-3.12", "Kokoro needs < 3.13: use python3.12 (uv venv -p 3.12 .venv)")
    for name, extra in [("fastapi", "app"), ("pipecat", "app"), ("cryptography", "app"), ("chromadb", "app"), ("crawl4ai", "app"),
                        ("anthropic", "app"), ("faster_whisper", "stt-whisper"), ("kokoro", "tts-kokoro")]:
        line("PASS" if mod(name) else "MISSING", f"python package {name}", f'pip install -e ".[{extra}]"')
    for name, extra, note in [("transformers", "stt-indic", "transformers package (IndicConformer runtime; weights checked below)"), ("parler_tts", "tts-parler", "Indic Parler-TTS (hi/bn/kn voices, GPU)"),
                              ("omnivoice", "tts-omnivoice", "OmniVoice (DEMO ONLY, CC-BY-NC weights, GPU)"), ("sentence_transformers", "retrieval", "BGE-M3 embeddings")]:
        line("PASS" if mod(name) else "PENDING", f"{note}", f'pip install -e ".[{extra}]"')
    for b, fix in [("ffmpeg", "sudo apt install ffmpeg"), ("espeak-ng", "sudo apt install espeak-ng"), ("node", "install Node.js 20+ (nvm)")]:
        line("PASS" if shutil.which(b) else "MISSING", f"binary {b}", fix)
    try:
        import unidic
        ok = pathlib.Path(unidic.DICDIR, "mecabrc").exists()
    except Exception:
        ok = False
    line("PASS" if ok else "MISSING", "UniDic dictionary (Kokoro Japanese)", "python -m unidic download")
    for repo, what in [("Systran/faster-whisper-small", "Whisper small (CPU profile)"), ("Systran/faster-whisper-large-v3", "Whisper large-v3 (GPU profile)"),
                       ("hexgrad/Kokoro-82M", "Kokoro weights"), ("BAAI/bge-m3", "BGE-M3 weights"),
                       ("ai4bharat/indic-conformer-600m-multilingual", "IndicConformer weights (gated: HF_TOKEN)"),
                       ("ai4bharat/indic-parler-tts", "Indic Parler weights (gated: HF_TOKEN)"), ("k2-fsa/OmniVoice", "OmniVoice weights (demo only)")]:
        line("PASS" if hf_cached(repo) else "PENDING", what, f"scripts/download_models.sh  (repo {repo})")
    try:
        os.environ.setdefault("SHAON_NO_SEED", "1")
        from api.config import load_config
        from api.db import DB
        from api.secrets_store import SecretStore
        cfg = load_config()
        key, src = (SecretStore(DB(cfg.data_dir / "shaon.sqlite3"), cfg.data_dir).api_key() if cfg.data_dir.exists() else (os.environ.get("ANTHROPIC_API_KEY"), "env"))
        line("PASS" if key else "PENDING", f"Anthropic API key ({src if key else 'not set'})", "open Settings in the app and paste the key, then press Test key")
    except Exception as e:
        line("PENDING", f"Anthropic API key (could not read: {e})")
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        out = ""
    line("PASS" if out else "PENDING", f"NVIDIA GPU {out or 'not found'}", "no GPU: CPU profile works for en/ja; run M0 on Kaggle (eval/kaggle_m0.md)")
    line("PASS" if (ROOT / "web" / "out" / "index.html").exists() else "MISSING", "web UI built", "cd web && npm ci && npm run build  (scripts/start.sh does it)")
    print("\nThe app runs in honest demo mode with any PENDING item; the banner and Settings > Engines say what is missing.")


if __name__ == "__main__":
    main()
