"""Helpers for scripts/share.ps1 (kept in Python so the launcher stays small and ASCII-only).

  python scripts/share_helper.py qr <url> <png_path>      # terminal QR + PNG (segno, BSD-3)
  python scripts/share_helper.py status <port>            # one status line from the launcher-only endpoint
  python scripts/share_helper.py ready <port>             # exit 0 when every language is ready, prints per-language states
  python scripts/share_helper.py passcode                 # random visitor passcode, e.g. k7mq-x3fp-9tbw
  python scripts/share_helper.py preload                  # SHAON_PRELOAD for the languages whose models are on disk
  python scripts/share_helper.py key                      # exit 0 if an Anthropic key is configured (prints yes/no only)
"""
from __future__ import annotations

import json
import secrets
import sys
import urllib.request

ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i
LANGS = ["en", "ja", "hi", "bn", "kn"]


def local(port: str) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/share/status", timeout=20) as r:
        return json.loads(r.read())


def main() -> int:
    cmd = sys.argv[1]
    if cmd == "qr":
        import segno

        url, png = sys.argv[2], sys.argv[3]
        q = segno.make(url, error="m")
        q.save(png, scale=8, border=2)
        try:
            q.terminal(compact=True)
        except Exception:  # some legacy Windows consoles cannot draw the block characters
            print("(open the QR image instead:", png, ")")
        return 0
    if cmd == "passcode":
        print("-".join("".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3)))
        return 0
    if cmd == "preload":  # only warm what is downloaded; missing languages show as 'missing' in the app
        import pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from agent.engines import weights_cached
        have = {"en": weights_cached("Systran/faster-whisper-small") and weights_cached("hexgrad/Kokoro-82M")}
        have["ja"] = have["en"]
        for l, iso in (("hi", "hin"), ("bn", "ben"), ("kn", "kan")):
            have[l] = weights_cached("facebook/mms-1b-all") and (weights_cached(f"facebook/mms-tts-{iso}") or (l == "hi" and have["en"]))
        items = (["lid"] if have["en"] else []) + [f"{k}:{l}" for l in LANGS if have[l] for k in ("stt", "tts")]
        print(",".join(items))
        return 0
    if cmd == "key":  # reads the encrypted store directly (no server needed); prints yes/no, never the key
        try:
            import os
            import pathlib
            sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
            from api.config import load_config
            from api.db import DB
            from api.secrets_store import SecretStore
            cfg = load_config()
            cfg.data_dir.mkdir(parents=True, exist_ok=True)
            key, _src = SecretStore(DB(cfg.data_dir / "shaon.sqlite3"), cfg.data_dir).api_key()
            ok = bool(key) or bool(os.environ.get("ANTHROPIC_API_KEY"))
        except Exception as e:
            print(f"could not read the key store ({type(e).__name__})")
            return 2
        print("yes" if ok else "no")
        return 0 if ok else 1
    if cmd in ("status", "ready"):
        try:
            s = local(sys.argv[2])
        except TimeoutError:
            print("app is busy loading models...")
            return 2
        except Exception as e:
            print(f"app not answering ({type(e).__name__})")
            return 2
        langs = s["languages"]
        parts = " ".join(f"{l}:{langs[l]['state']}" for l in LANGS)
        if cmd == "ready":  # 0 = all ready, 3 = settled but some not downloaded/unavailable, 1 = still loading
            print(parts)
            states = [langs[l]["state"] for l in LANGS]
            if all(s == "ready" for s in states):
                return 0
            return 3 if all(s in ("ready", "missing", "unavailable") for s in states) else 1
        sp = s.get("spend", {})
        print(f"engines {parts} | calls {s['active_calls']}/{s['max_calls']} | llm {s['provider']} | "
              f"spend ${sp.get('spent_usd', 0):.2f} of ${sp.get('cap_usd', 0):.2f}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
