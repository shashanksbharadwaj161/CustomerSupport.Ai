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
