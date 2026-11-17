"""Runs the REAL launcher (scripts/share.ps1) under PowerShell 7 with a stub cloudflared (the sandbox cannot reach
Cloudflare's edge). Checks: link + passcode printed, share-link.txt content (no admin passcode), the tunnel drop is
detected and a NEW link is printed, everything is stopped at the end.
  python tests/share/run_launcher_test.py [path/to/pwsh]
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main() -> int:
    pwsh = sys.argv[1] if len(sys.argv) > 1 else shutil.which("pwsh")
    if not pwsh:
        print("SKIP: pwsh not installed")
        return 0
    out = pathlib.Path(tempfile.mkdtemp())
    env = {**os.environ, "SHAON_LLM_PROVIDER": "fake", "SHAON_DATA_DIR": tempfile.mkdtemp(), "FAKE_CF_STATE": str(out / "runs"),
           "FAKE_CF_DROP_AFTER": "12", "ADMIN_PASSWORD": ""}
    r = subprocess.run([pwsh, "-NoProfile", "-File", "scripts/share.ps1", "-Port", "8771", "-Cloudflared", str(ROOT / "tests/share/fake_cloudflared.sh"),
                        "-PublicUrlOverride", "http://127.0.0.1:8771", "-RunSeconds", "45", "-SkipWarmup", "-OutDir", str(out)],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=300, input="")  # stdin EOF = no keyboard
    log = r.stdout + r.stderr
    visitor = re.search(r"VISITOR PASSCODE:\s+(\S+)", log)
    admin = re.search(r"Admin passcode.*?: (\S+)", log)
    link_txt = (out / "share-link.txt").read_text() if (out / "share-link.txt").exists() else ""
    checks = {
        "first_run_key_step_points_to_local_settings": "http://127.0.0.1:8771/settings/" in log and "Never type or paste the key" in log,
        "no_keyboard_does_not_hang": "Continuing without a key" in log,
        "printed_link_and_passcode": "SHARE THIS LINK:   https://stub-run-1-test.trycloudflare.com/call/" in log and bool(visitor),
        "drop_detected_old_link_dead": "TUNNEL DROPPED. The old link is DEAD: https://stub-run-1-test" in log,
        "new_link_printed": "SHARE THIS LINK:   https://stub-run-2-test.trycloudflare.com/call/" in log,
        "share_link_txt_has_new_link_and_passcode": "stub-run-2-test" in link_txt and bool(visitor) and visitor.group(1) in link_txt,
        "share_link_txt_has_no_admin_passcode": bool(admin) and admin.group(1) not in link_txt,
        "qr_png_written": (out / "share-qr.png").exists(),
        "stopped_cleanly": "Stopped. The link no longer works." in log and subprocess.run(["pgrep", "-f", "port 8771"], capture_output=True).returncode != 0,
    }
    for k, v in checks.items():
        print(f"{k:<45} {'PASS' if v else 'FAIL'}")
    if not all(checks.values()):
        print(log[-3000:])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
