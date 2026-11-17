"""Share-mode visitor UI E2E: wrong passcode, Get-ready checks, busy (max 1 call), max call length (20 s),
host PC going offline mid-call (the app is killed). Fake LLM, CPU engines, real browser.
  python tests/e2e/run_share_ui_e2e.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PORT = int(os.environ.get("E2E_PORT", "8769"))


def main() -> int:
    py = os.environ.get("PYTHON") or sys.executable
    wav = ROOT / "tests" / "e2e" / "audio" / "en_question.wav"
    if not wav.exists():
        subprocess.run([py, "tests/e2e/make_fake_mic.py", str(wav.parent)], cwd=ROOT, check=True)
    data = pathlib.Path(tempfile.mkdtemp())
    (data / "share_host.txt").write_text("ui-e2e.trycloudflare.com")
    env = {**os.environ, "SHAON_DATA_DIR": str(data), "SHAON_LLM_PROVIDER": "fake", "SHAON_SEED_DEMO": "0", "SHAON_EXPOSED": "1",
           "ALLOW_KEY_EDIT": "false", "VISITOR_PASSCODE": "ui-visit-pass", "ADMIN_PASSWORD": "ui-admin-passcode-1",
           "SHAON_SHARE_HOST_FILE": str(data / "share_host.txt"), "SHAON_MAX_CALLS": "1", "SHAON_MAX_CALL_SECONDS": "20",
           "SHAON_PRELOAD": "lid,stt:en,tts:en"}
    srv = subprocess.Popen([py, "-m", "uvicorn", "--factory", "api.main:create_app", "--port", str(PORT), "--log-level", "warning"],
                           cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    results = []
    try:
        for _ in range(120):
            try:
                s = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/share/status", timeout=20).read())
                if s["languages"]["en"]["state"] == "ready":
                    break
            except Exception:
                pass
            time.sleep(2)
        node = subprocess.Popen(["node", "scripts/share_ui_e2e.mjs", f"http://127.0.0.1:{PORT}", "ui-visit-pass", str(wav)],
                                cwd=ROOT / "web", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in node.stdout:
            line = line.strip()
            if line == "KILL_SERVER":
                srv.kill()
                continue
            if line.startswith("{"):
                r = json.loads(line)
                results.append(r)
                print(f"{r['check']:<40} {'PASS' if r['ok'] else 'FAIL'}  {json.dumps({k: v for k, v in r.items() if k not in ('check', 'ok')}, ensure_ascii=False)[:150]}")
        node.wait(timeout=60)
    finally:
        if srv.poll() is None:
            srv.kill()
    from eval.common import save
    sys.path.insert(0, str(ROOT))
    save("share_ui_e2e", {"kind": "share_ui_e2e", "checks": results})
    return 0 if results and len(results) == 5 and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
