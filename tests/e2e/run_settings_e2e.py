#!/usr/bin/env python3
"""Starts a LOCAL PREVIEW server (no passcode, empty data dir, demo seeding off) and runs web/scripts/settings_e2e.mjs
with a FAKE key. No Anthropic call is made: the test never presses Test key, never refreshes models, never starts a
call. Afterwards the server logs are checked for the fake key too."""
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PORT = 8431
FAKE_KEY = "sk-ant-api03-E2E-FAKE-KEY-not-real-0000000000wxyz"


def main() -> int:
    data = tempfile.mkdtemp()
    log = pathlib.Path(data) / "server.log"
    env = {**os.environ, "SHAON_LOCAL_PREVIEW": "1", "SHAON_DATA_DIR": data, "SHAON_SEED_DEMO": "0", "SHAON_LLM_PROVIDER": "",
           "ANTHROPIC_API_KEY": "", "SHAON_PRELOAD": "", "ADMIN_PASSWORD": "", "VISITOR_PASSCODE": ""}
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "--factory", "api.main:create_app", "--host", "127.0.0.1", "--port", str(PORT),
                            "--log-level", "info"], cwd=ROOT, env=env, stdout=open(log, "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        r = subprocess.run(["node", "scripts/settings_e2e.mjs", f"http://127.0.0.1:{PORT}", FAKE_KEY], cwd=ROOT / "web")
        code = r.returncode
    finally:
        srv.terminate()
        srv.wait(timeout=20)
    leaked = FAKE_KEY in log.read_text(errors="ignore")
    print(f"{'fake key never in server log'.ljust(48)} {'FAIL' if leaked else 'PASS'}")
    return 1 if (code or leaked) else 0


if __name__ == "__main__":
    sys.exit(main())
