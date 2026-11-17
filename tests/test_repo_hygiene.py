"""Every tracked file must check out on Windows: no reserved characters or trailing dots/spaces in names."""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
BAD = re.compile(r'[<>:"|?*\\]|[. ]$')


def test_tracked_filenames_are_windows_safe():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    bad = [f for f in files if any(BAD.search(part) for part in f.split("/"))]
    assert not bad, f"not valid on Windows: {bad[:10]}"
