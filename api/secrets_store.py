"""Encrypted-at-rest secrets (the Anthropic API key).

- A Fernet key is generated on first run into data/secret.key with mode 0600.
- The API key is stored encrypted in the settings table; it is never returned to the browser
  (only the last 4 characters) and is scrubbed from logs (agent/logscrub.py).
- Resolution order: DB value, then ANTHROPIC_API_KEY from the environment/.env.
"""
from __future__ import annotations

import os
import pathlib

from cryptography.fernet import Fernet, InvalidToken

from api.db import DB, now

KEY_NAME = "anthropic_api_key"


class SecretStore:
    def __init__(self, db: DB, data_dir: pathlib.Path):
        self.db = db
        self.key_file = data_dir / "secret.key"
        self._fernet = Fernet(self._load_or_create())

    def _load_or_create(self) -> bytes:
        if self.key_file.exists():
            return self.key_file.read_bytes().strip()
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        k = Fernet.generate_key()
        fd = os.open(self.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(k)
        try:
            os.chmod(self.key_file, 0o600)
        except OSError:
            pass
        return k

    def file_mode(self) -> int:
        return self.key_file.stat().st_mode & 0o777

    def set(self, name: str, value: str) -> None:
        token = self._fernet.encrypt(value.encode()).decode()
        self.db.execute("INSERT INTO settings(key,value,encrypted,updated_at) VALUES(?,?,1,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, encrypted=1, updated_at=excluded.updated_at",
                        (name, token, now()))

    def get(self, name: str) -> str | None:
        r = self.db.one("SELECT value, encrypted FROM settings WHERE key=?", (name,))
        if not r or not r["value"]:
            return None
        if not r["encrypted"]:
            return r["value"]
        try:
            return self._fernet.decrypt(r["value"].encode()).decode()
        except InvalidToken:
            return None  # secret.key replaced: stored value unreadable, treat as missing

    def delete(self, name: str) -> None:
        self.db.execute("DELETE FROM settings WHERE key=?", (name,))

    # API key helpers
    def api_key(self) -> tuple[str | None, str]:
        """(key, source) where source is 'settings', 'env' or 'none'."""
        k = self.get(KEY_NAME)
        if k:
            return k, "settings"
        env = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if env:
            return env, "env"
        return None, "none"

    @staticmethod
    def last4(key: str | None) -> str | None:
        return key[-4:] if key else None
