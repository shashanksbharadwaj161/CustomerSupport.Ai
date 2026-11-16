"""Audio I/O helpers. Decoding/resampling goes through ffmpeg so any input format works."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np


def load_audio(path: str, sr: int = 16000) -> np.ndarray:
    """Decode any audio file to mono float32 at `sr` Hz."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH")
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path,
           "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def write_wav(path: str, audio: np.ndarray, sr: int) -> None:
    import soundfile as sf

    sf.write(path, np.asarray(audio, dtype=np.float32), sr)
