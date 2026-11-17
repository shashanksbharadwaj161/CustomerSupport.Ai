#!/usr/bin/env python3
"""Installer logic test: runs scripts/install.ps1 under PowerShell 7 with winget, git clone, Python, npm and cloudflared
STUBBED (tests/install/stubs), each scenario on its own fake 'machine' (HOME, PATH, state dir).

  PWSH=/path/to/pwsh PYTHON=/path/to/venv/python python tests/install/run_installer_test.py

Scenarios: low disk, winget missing, private-repo clone failure, fresh machine (with a failed model download),
second run (resumes the download, self-test, first-run key step, hands off to the share launcher -> link),
third run (everything skipped, key configured, key never printed), partially installed + ZIP folder + main merged.
Not covered (cannot run here): real winget, Windows 10/11, Windows PowerShell 5.1, the real tunnel, a real phone.
Writes eval/out/installer_test.json.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
STUBS = ROOT / "tests/install/stubs"
PWSH = os.environ.get("PWSH") or shutil.which("pwsh") or "pwsh"
REAL_PY = os.environ.get("PYTHON") or sys.executable
BRANCH = "claude/sweet-ptolemy-7qza59"
FAKE_KEY = "sk-ant-test-FAKEKEY-0123456789abcdef"  # not a real key; must never show up in any output
FACTS = {"os": "Microsoft Windows 11 Home (build 26100) [stub]", "build": 26100, "free_gb": 120, "ram_gb": 16,
         "cpu": "Stub CPU", "cores": 8, "gpu": "Intel(R) UHD Graphics", "nvidia": False, "internet": True}
results: list[dict] = []


def git(*a, cwd=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    subprocess.run(["git", *a], cwd=cwd, env=env, check=True, capture_output=True)


def make_fixture(tmp: pathlib.Path) -> tuple[str, str, pathlib.Path]:
    """Repo with the CURRENT working tree (tracked + new files), as bare remotes: one with only the work branch,
    one where main also exists (merged). Returns file:// URLs and the plain source tree (= a 'ZIP download')."""
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    src = tmp / "src"
    for f in filter(None, files):
        p = ROOT / f
        if p.is_file():
            (src / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, src / f)
    zipcopy = tmp / "zip"
    shutil.copytree(src, zipcopy)
    git("init", "-q", "-b", BRANCH, cwd=src)
    git("add", "-A", cwd=src)
    git("commit", "-q", "-m", "fixture", cwd=src)
    feat, both = tmp / "feature.git", tmp / "with-main.git"
    git("clone", "-q", "--bare", str(src), str(feat))
    git("clone", "-q", "--bare", str(src), str(both))
    git("branch", "main", BRANCH, cwd=both)
    return feat.as_uri(), both.as_uri(), zipcopy


class Machine:
    def __init__(self, base: pathlib.Path, name: str, preinstalled=(), winget=True, facts=None):
        self.dir = base / name
        self.home, self.state, self.inst, self.bin = (self.dir / d for d in ("home", "state", "installed", "bin"))
        for d in (self.home, self.state, self.inst, self.bin, self.dir / "tmp"):
            d.mkdir(parents=True, exist_ok=True)
        if winget:
            shutil.copy(STUBS / "winget", self.bin / "winget")
        for t in preinstalled:
            shutil.copy(STUBS / "tools" / t, self.inst / t)
        self.path_file = self.dir / "path.txt"
        if preinstalled:
            self.path_file.write_text(str(self.inst) + "\n")
        self.facts = self.dir / "facts.json"
        self.facts.write_text(json.dumps({**FACTS, **(facts or {})}))

    def run(self, script: pathlib.Path, args: str = "", extra_env=None, stdin="", timeout=300):
        path = str(self.bin)
        if self.path_file.exists():
            path = os.pathsep.join(self.path_file.read_text().split() + [path])
        env = {"PATH": path, "HOME": str(self.home), "TMPDIR": str(self.dir / "tmp"), "LANG": "C.UTF-8",
               "FAKE_STATE": str(self.state), "FAKE_STUBS": str(STUBS), "FAKE_INSTALLED": str(self.inst), "SHAON_TEST_PATH_FILE": str(self.path_file),
               "SHAON_TEST_FACTS": str(self.facts), "FAKE_CF_STATE": str(self.dir / "cf_runs"),
               "PYTHON": REAL_PY, "SHAON_SEED_DEMO": "0", "SHAON_LLM_PROVIDER": "fake",
               "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), **(extra_env or {})}
        hf = os.environ.get("HF_HOME")
        if hf:
            env["HF_HOME"] = hf
        cmd = f"& '{script}' {args}; exit $LASTEXITCODE"
        t0 = time.time()
        r = subprocess.run([PWSH, "-NoProfile", "-Command", cmd], input=stdin, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout + r.stderr, round(time.time() - t0, 1)

    def log(self, name):
        p = self.state / name
        return p.read_text() if p.exists() else ""


def check(scenario, name, ok, detail=""):
    results.append({"scenario": scenario, "check": name, "pass": bool(ok), "detail": str(detail)[:300]})
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   [{str(detail)[:300]}]"), flush=True)


def tail(out, n=25):
    return "\n".join(out.strip().splitlines()[-n:])


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="shaon-installer-test-"))
    feat_url, main_url, zipsrc = make_fixture(tmp)
    dl = tmp / "download"           # a downloaded installer outside any ShaOn folder (the one-line command)
    dl.mkdir()
    shutil.copy(ROOT / "scripts/install.ps1", dl / "install.ps1")
    boot = dl / "install.ps1"
    port = 8231
    share_args = (f"-ShareArgs @('-Port','{port}','-SkipWarmup','-RunSeconds','25','-OutDir','{tmp / 'out'}',"
                  f"'-PublicUrlOverride','http://127.0.0.1:{port}')")
    (tmp / "out").mkdir()

    print("== 1. low disk (9 GB free): stops before installing anything")
    m = Machine(tmp, "lowdisk", facts={"free_gb": 9})
    rc, out, _ = m.run(boot, f"-RepoUrl '{feat_url}' -NonInteractive")
    check("low_disk", "exit code 1", rc == 1, tail(out))
    check("low_disk", "plain message about disk space", "not enough free disk space" in out and "20 GB" in out, tail(out))
    check("low_disk", "result table printed first", "Free disk" in out and "STOP" in out, tail(out))
    check("low_disk", "nothing installed or cloned", not m.log("winget.log") and not (m.home / "ShaOn").exists(), m.log("winget.log"))

    print("== 2. winget missing on a bare PC")
    m = Machine(tmp, "nowinget", winget=False)
    rc, out, _ = m.run(boot, f"-RepoUrl '{feat_url}' -NonInteractive")
    check("no_winget", "exit code 1", rc == 1, tail(out))
    check("no_winget", "exact Microsoft Store link", "https://apps.microsoft.com/detail/9NBLGGH4NNS1" in out, tail(out))

    print("== 3. private repository: clone refused")
    m = Machine(tmp, "private", preinstalled=["git", "python3.12", "node", "npm", "cloudflared", "espeak-ng", "ffmpeg", "shaon-vcredist"])
    rc, out, _ = m.run(boot, f"-RepoUrl 'https://github.com/owner/private.git' -NonInteractive", {"FAKE_GIT_CLONE_FAIL": "auth"})
    check("private_repo", "exit code 1", rc == 1, tail(out))
    check("private_repo", "says the repository may be private", "may be private" in out, tail(out))
    check("private_repo", "exact sign-in steps (Git Credential Manager, gh auth login, gh auth setup-git)",
          all(s in out for s in ("Git Credential Manager", "gh auth login", "gh auth setup-git", "Download ZIP")), tail(out))
    check("private_repo", "no traceback / stack trace", "at line" not in out.lower() and "Traceback" not in out, tail(out))
    check("private_repo", "winget not called (all tools present)", not m.log("winget.log"), m.log("winget.log"))

    print("== 4. fresh machine: install everything; the model download fails half-way")
    m = Machine(tmp, "fresh")
    rc, out, t_fresh = m.run(boot, f"-RepoUrl '{feat_url}'", {"FAKE_FETCH_FAIL_ONCE": "1"}, stdin="\n")
    wl = m.log("winget.log")
    ids = ["Git.Git", "Python.Python.3.12", "OpenJS.NodeJS.LTS", "Cloudflare.cloudflared", "eSpeak-NG.eSpeak-NG", "Gyan.FFmpeg", "Microsoft.VCRedist.2015+.x64"]
    check("fresh", "winget installed all 7 tools", all(f"install {i} " in wl for i in ids), wl)
    check("fresh", "winget agreements accepted non-interactively", wl.count("--accept-package-agreements --accept-source-agreements") == 7, wl)
    check("fresh", "PATH refreshed in the same session (tools found right after install)", "Python 3.12.10 at" in out, tail(out))
    check("fresh", "cloned the work branch and said why", f"Cloning branch {BRANCH} (no main branch yet)" in out, tail(out))
    check("fresh", "venv + pinned pip install", (m.home / "ShaOn/.venv/bin/python").exists() and "-c deploy/requirements-cpu.txt" in m.log("python.log"), m.log("python.log"))
    check("fresh", "torch from the CPU index", "download.pytorch.org/whl/cpu" in m.log("python.log"), m.log("python.log"))
    check("fresh", "web app built (npm ci + build)", "npm ci" in m.log("npm.log") and "npm run build" in m.log("npm.log"), m.log("npm.log"))
    check("fresh", "HF token asked once, skipped on Enter", "Skipped (you can add it later" in out, tail(out))
    check("fresh", "total download size shown before downloading", "5.69 GB in total" in out, tail(out))
    check("fresh", "stops on the failed download with a plain resume message", rc == 1 and "resumes where it stopped" in out, tail(out))
    check("fresh", ".env says CPU demo mode", "SHAON_DEVICE=cpu" in (m.home / "ShaOn/.env").read_text(), "")

    print("== 5. second run: resumes the download, self-test, first-run key step, share link")
    pip_before = m.log("pip_installs").count("x")
    rc, out, t_second = m.run(boot, f"-RepoUrl '{feat_url}' {share_args}", stdin="\n" + "skip\n", timeout=400)
    check("second_run", "winget not called again", m.log("winget.log") == wl, m.log("winget.log"))
    check("second_run", "git pull --ff-only on the existing checkout", "pull --ff-only" in m.log("git.log") and "Code is up to date" in out, tail(out))
    check("second_run", "pip skipped (pinned set unchanged)", m.log("pip_installs").count("x") == pip_before and "already installed" in out, tail(out))
    check("second_run", "web build skipped", m.log("npm.log").count("npm run build") == 1, m.log("npm.log"))
    check("second_run", "download resumed and finished", "resuming at" in out and "All models downloaded" in out, tail(out))
    check("second_run", "self-test ran and passed", "Self-test passed" in out, tail(out))
    check("second_run", "first-run key step: local Settings URL + admin passcode, never asks for the key here",
          f"http://127.0.0.1:{port}/settings/" in out and "Never type or paste the key into THIS window" in out, tail(out, 60))
    check("second_run", "Enter without a key -> 'No key found yet'", "No key found yet" in out, tail(out, 60))
    check("second_run", "spend-limit reminder", "spend limit" in out, tail(out, 60))
    check("second_run", "ends with the public link + visitor passcode + QR", "SHARE THIS LINK:   https://stub-run-1-test.trycloudflare.com/call/" in out
          and "VISITOR PASSCODE:" in out and (tmp / "out/share-qr.png").exists(), tail(out, 40))

    print("== 6. third run: everything skipped; key configured; the key is never printed")
    env_file = m.home / "ShaOn/.env"
    env_file.write_text(env_file.read_text() + f"\nANTHROPIC_API_KEY={FAKE_KEY}\n")
    (m.dir / "cf_runs").unlink(missing_ok=True)
    rc, out, t_third = m.run(boot, f"-RepoUrl '{feat_url}' -NonInteractive {share_args}", timeout=300)
    check("third_run", "self-test skipped (already passed for this version)", "Self-test already passed" in out, tail(out))
    check("third_run", "models: nothing to download", "Nothing to download" in out, tail(out))
    check("third_run", "key step skipped: 'Anthropic key: configured'", "Anthropic key: configured" in out, tail(out, 60))
    check("third_run", "link printed", "SHARE THIS LINK:" in out, tail(out, 40))
    leaks = [str(p) for p in [*(m.home / "ShaOn/data").rglob("*.log"), m.dir / "tmp/shaon-install/install.log", tmp / "out/share-link.txt"]
             if p.exists() and FAKE_KEY in p.read_text(errors="ignore")]
    check("third_run", "API key never in output, logs or share-link.txt", FAKE_KEY not in out and not leaks, leaks)
    check("third_run", f"installer part fast on later runs (installer+launcher {t_third} s incl. 25 s share run)", t_third < 150, t_third)

    print("== 7. partially installed PC (Git + Node present), unzipped download, main merged")
    m = Machine(tmp, "partial", preinstalled=["git", "node", "npm"])
    zdir = m.dir / "ShaOn-main"
    shutil.copytree(zipsrc, zdir)
    rc, out, _ = m.run(zdir / "scripts/install.ps1", f"-RepoUrl '{main_url}' -NonInteractive -NoShare")
    wl = m.log("winget.log")
    check("partial", "only the missing 5 tools installed", "Git.Git" not in wl and "NodeJS" not in wl and wl.count("install ") == 5, wl)
    check("partial", "present tools skipped", "Git           present" in out and "Node.js LTS   present" in out, tail(out))
    check("partial", "ZIP folder connected to git in place", (zdir / ".git").exists() and "not a git checkout (ZIP download)" in out, tail(out))
    check("partial", "detects main was merged and uses it", "branch main (main contains the installer" in out, tail(out))
    check("partial", "finishes (-NoShare)", rc == 0 and "Done (-NoShare)" in out, tail(out))

    print("== 8. pip failure gives a plain explanation")
    m = Machine(tmp, "pipfail", preinstalled=["git", "python3.12", "node", "npm", "cloudflared", "espeak-ng", "ffmpeg", "shaon-vcredist"])
    rc, out, _ = m.run(boot, f"-RepoUrl '{feat_url}' -NonInteractive -NoShare", {"FAKE_PIP_FAIL": "1"})
    check("pip_fail", "stops with a plain explanation", rc == 1 and "Python packages did not install" in out and "Traceback" not in out, tail(out))

    total = len(results)
    passed = sum(r["pass"] for r in results)
    print(f"\n{passed}/{total} checks passed. Times: fresh run {t_fresh} s (stopped at models), second run {t_second} s, third run {t_third} s (stubs).")
    out_dir = ROOT / "eval/out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "installer_test.json").write_text(json.dumps({
        "kind": "installer_test", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pwsh": PWSH,
        "note": "PowerShell 7 on Linux with stubbed winget/git clone/python/npm/cloudflared; real git for pull/fetch; real app server for the share hand-off.",
        "not_tested": ["real winget", "Windows 10/11", "Windows PowerShell 5.1", "real Cloudflare tunnel", "real phone"],
        "passed": passed, "total": total, "results": results}, indent=1))
    if os.environ.get("KEEP_TMP") is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
