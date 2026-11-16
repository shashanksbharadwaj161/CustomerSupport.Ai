import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SHAON_DATA_DIR", str(tmp_path / "data"))
    for k in ("ANTHROPIC_API_KEY", "ADMIN_PASSWORD", "SHAON_LLM_PROVIDER", "ALLOW_KEY_EDIT", "SHAON_EXPOSED",
              "TRANSPORT", "SHAON_PRELOAD", "CRAWL_ALLOWLIST"):
        monkeypatch.setenv(k, "")
    return tmp_path / "data"


def make_client(provider=None, **env):
    from fastapi.testclient import TestClient

    for k, v in env.items():
        os.environ[k] = v
    from api.main import create_app
    from api.state import AppState

    app = create_app(AppState(provider_override=provider))
    return TestClient(app), app


if pathlib.Path("/opt/pw-browsers").exists():  # this dev VM's preinstalled Chromium (CI / user machines use `playwright install`)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
os.environ.setdefault("SHAON_EMBEDDER", "hash")  # fast tests; BGE-M3 is exercised by eval/runners/run_retrieval.py


@pytest.fixture(scope="session")
def sites():
    """Serve each fake site from its own root on a local port (own robots.txt, own host:port)."""
    import functools
    import http.server
    import threading

    base = ROOT / "eval" / "fixtures" / "sites"
    servers, urls = [], {}
    for name in ("lotus-bank", "lotus-travel", "lotus-js"):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(base / name))
        handler.log_message = lambda *a, **k: None
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        urls[name] = f"http://127.0.0.1:{srv.server_address[1]}/"
    yield urls
    for s in servers:
        s.shutdown()
