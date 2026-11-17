#!/usr/bin/env python3
"""Runs the REAL local-preview launcher (scripts/local.ps1) under PowerShell 7 with STALE gate settings in the
environment (ADMIN_PASSWORD, VISITOR_PASSCODE, SHAON_EXPOSED=1, ALLOW_KEY_EDIT=false, SPEND_CAP_USD=0) and checks that
the app still opens without a passcode, Settings is editable, the cap is the default and tunnel-forwarded requests
are refused.   usage: run_local_test.py /path/to/pwsh"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PORT = 8345


def get(path, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception:
        return 0, ""


def main() -> int:
    pwsh = sys.argv[1] if len(sys.argv) > 1 else shutil.which("pwsh")
    if not pwsh:
        print("SKIP: pwsh not installed")
        return 0
    env = {**os.environ, "SHAON_DATA_DIR": tempfile.mkdtemp(), "SHAON_SEED_DEMO": "0", "ADMIN_PASSWORD": "stale-admin-123456",
           "VISITOR_PASSCODE": "stale-visitor", "SHAON_EXPOSED": "1", "ALLOW_KEY_EDIT": "false", "SPEND_CAP_USD": "0"}
    p = subprocess.Popen([pwsh, "-NoProfile", "-File", "scripts/local.ps1", "-Port", str(PORT), "-NoBrowser", "-RunSeconds", "40"],
                         cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(180):
        if get("/health")[0] == 200:
            break
        time.sleep(1)
    status = json.loads(get("/api/auth/status")[1] or "{}")
    code, body = get("/api/settings")
    s = json.loads(body or "{}")
    checks = {
        "no_passcode_gate": status.get("required") is False and status.get("local_preview") is True,
        "settings_editable": code == 200 and s.get("key_edit_allowed") is True,
        "default_cap_not_zero": s.get("spend", {}).get("cap_usd") == 10,
        "pages_open": all(get(p)[0] == 200 for p in ("/", "/call/", "/studio/", "/knowledge/", "/logs/", "/settings/")),
        "forwarded_request_refused": get("/api/settings", {"CF-Connecting-IP": "203.0.113.9"})[0] == 403,
    }
    out = p.communicate(timeout=120)[0]
    checks["printed_settings_url"] = f"http://127.0.0.1:{PORT}/settings/" in out
    checks["stopped_cleanly"] = "Stopped." in out and get("/health")[0] == 0
    for k, v in checks.items():
        print(f"{k:<32} {'PASS' if v else 'FAIL'}")
    if not all(checks.values()):
        print(out[-3000:])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
