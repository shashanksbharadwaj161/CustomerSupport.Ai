#!/usr/bin/env python3
"""Check this machine for the M0 bake-off and the live demo. Free, read-only, no network.

Rule ($0 plan, DEPLOY.md): NVIDIA GPU with >= 12 GB VRAM -> run M0 locally.
Otherwise -> run the M0 batch scripts on a free Kaggle GPU notebook (Colab free as backup).
Nothing paid is ever started by this script.

  python scripts/check_hardware.py          # prints a summary, writes eval/out/hardware.json
"""
from __future__ import annotations

import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys

MIN_VRAM_MB = 12 * 1024
ROOT = pathlib.Path(__file__).resolve().parent.parent


def nvidia_gpus() -> list[dict]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True,
                             timeout=10, check=True).stdout
    except Exception:
        return []
    gpus = []
    for row in out.strip().splitlines():
        name, mem, drv = [x.strip() for x in row.split(",")]
        gpus.append({"name": name, "vram_mb": int(float(mem)), "driver": drv})
    return gpus


def ram_gb() -> float | None:
    try:
        import psutil

        return round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        pass
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal"):
                return round(int(line.split()[1]) / 2**20, 1)
    except OSError:
        pass
    if sys.platform == "darwin":
        try:
            b = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
            return round(b / 2**30, 1)
        except Exception:
            pass
    return None


def is_wsl() -> bool:
    try:
        return "microsoft" in open("/proc/version").read().lower()
    except OSError:
        return False


def torch_info() -> dict:
    try:
        import torch

        return {"version": torch.__version__, "cuda": torch.cuda.is_available(),
                "cuda_version": torch.version.cuda,
                "mps": bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())}
    except ImportError:
        return {"version": None}


def decide(gpus: list[dict], apple_silicon: bool) -> tuple[str, str]:
    best = max((g["vram_mb"] for g in gpus), default=0)
    if best >= MIN_VRAM_MB:
        return "local", f"NVIDIA GPU with {best} MB VRAM (>= {MIN_VRAM_MB} MB): run M0 on this machine."
    if gpus:
        why = f"NVIDIA GPU has only {best} MB VRAM (< {MIN_VRAM_MB} MB)."
    elif apple_silicon:
        why = "Apple Silicon, no NVIDIA GPU (MPS may run smaller models; measure before relying on it)."
    else:
        why = "No NVIDIA GPU."
    return "kaggle", (why + " Run the M0 batch scripts on a free Kaggle GPU notebook (eval/kaggle_m0.md); "
                      "Colab free as backup. Live demo models get chosen from M0 results for this machine.")


def main() -> int:
    gpus = nvidia_gpus()
    apple = sys.platform == "darwin" and platform.machine() == "arm64"
    decision, reason = decide(gpus, apple)
    disk = shutil.disk_usage(ROOT)
    info = {
        "kind": "hardware", "host": platform.node(), "os": f"{platform.system()} {platform.release()}",
        "wsl": is_wsl(), "arch": platform.machine(), "python": platform.python_version(),
        "cpu_count": os.cpu_count(), "ram_gb": ram_gb(), "gpus": gpus, "apple_silicon": apple,
        "torch": torch_info(), "ffmpeg": bool(shutil.which("ffmpeg")),
        "espeak_ng": bool(shutil.which("espeak-ng")), "disk_free_gb": round(disk.free / 2**30, 1),
        "decision": decision, "reason": reason,
    }
    out = ROOT / "eval" / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "hardware.json").write_text(json.dumps(info, indent=2))
    for k, v in info.items():
        if k not in ("kind", "reason"):
            print(f"{k:14} {v}")
    print(f"\n{reason}")
    if not info["ffmpeg"]:
        print("Install ffmpeg (needed to decode recordings).")
    if info["disk_free_gb"] < 40:
        print("Warning: under 40 GB free; all M0 model weights together need roughly 15-25 GB (estimate).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
