"""Runtime configuration from environment (.env is loaded by scripts/start.sh / python-dotenv-free loader)."""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv(path: pathlib.Path) -> None:
    """Minimal .env loader (no dependency). Existing env vars win; within the file the LAST line for a name wins
    (a value added below the empty template line must not be shadowed by it)."""
    if not path.exists():
        return
    vals: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in vals.items():
        os.environ.setdefault(k, v)


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None or v == "" else v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    data_dir: pathlib.Path
    admin_password: str
    allow_key_edit: bool
    transport: str  # smallwebrtc | websocket | both
    llm_model: str
    llm_fallback_model: str
    default_spend_cap_usd: float
    llm_provider: str  # auto | fake (tests / E2E only; shown in the banner)
    exposed: bool  # running behind a tunnel: crawler allowlist + no key edits from UI
    allowed_origins: list[str] = field(default_factory=list)
    crawl_allowlist: list[str] = field(default_factory=list)
    web_dir: pathlib.Path = ROOT / "web" / "out"
    preload: list[str] = field(default_factory=list)
    visitor_passcode: str = ""      # share mode: visitors may call; admin passcode needed for everything else
    max_calls: int = 2              # concurrent calls (busy screen beyond this)
    max_call_seconds: int = 300     # hard limit per call
    share_host_file: pathlib.Path | None = None  # public tunnel host learned at launch (written by scripts/share.ps1)


def load_config() -> Config:
    _load_dotenv(ROOT / ".env")
    data = pathlib.Path(os.environ.get("SHAON_DATA_DIR") or ROOT / "data").resolve()
    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return Config(
        data_dir=data,
        admin_password=os.environ.get("ADMIN_PASSWORD", ""),
        allow_key_edit=_bool("ALLOW_KEY_EDIT", True),
        transport=os.environ.get("TRANSPORT") or "both",
        llm_model=os.environ.get("LLM_MODEL") or "claude-haiku-5-5",
        llm_fallback_model=os.environ.get("LLM_FALLBACK_MODEL") or "claude-sonnet-5-5",
        default_spend_cap_usd=float(os.environ.get("SPEND_CAP_USD") or 10),
        llm_provider=os.environ.get("SHAON_LLM_PROVIDER") or "auto",
        exposed=_bool("SHAON_EXPOSED", False),
        allowed_origins=origins,
        crawl_allowlist=[d.strip().lower() for d in os.environ.get("CRAWL_ALLOWLIST", "").split(",") if d.strip()],
        preload=[p.strip() for p in os.environ.get("SHAON_PRELOAD", "").split(",") if p.strip()],
        visitor_passcode=os.environ.get("VISITOR_PASSCODE", ""),
        max_calls=int(os.environ.get("SHAON_MAX_CALLS") or 2),
        max_call_seconds=int(os.environ.get("SHAON_MAX_CALL_SECONDS") or 300),
        share_host_file=pathlib.Path(os.environ.get("SHAON_SHARE_HOST_FILE") or data / "share_host.txt"),
    )
