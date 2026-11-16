"""Agent profiles: one JSON document per profile, a new version on every save, rollback = new version."""
from __future__ import annotations

import json
import uuid

from agent.presets import PRESETS, normalize, preset
from api.db import DB, dumps, now


class ProfileStore:
    def __init__(self, db: DB):
        self.db = db

    def seed(self) -> None:
        if self.db.one("SELECT id FROM profiles LIMIT 1"):
            return
        self.create(preset("bank_support"), note="seed: bank demo", pid="lotus-bank")
        self.create(preset("tourism"), note="seed: tourism demo", pid="lotus-travel")

    def create(self, config: dict, note: str = "created", pid: str | None = None) -> dict:
        cfg = normalize(config)
        pid = pid or "agent_" + uuid.uuid4().hex[:10]
        t = now()
        self.db.execute("INSERT INTO profiles(id,name,type,created_at,updated_at,current_version) VALUES(?,?,?,?,?,1)",
                        (pid, cfg["name"] or "Untitled agent", cfg["type"], t, t))
        self.db.execute("INSERT INTO profile_versions(profile_id,version,config_json,note,created_at) VALUES(?,?,?,?,?)",
                        (pid, 1, dumps(cfg), note, t))
        return self.get(pid)

    def list(self) -> list[dict]:
        return self.db.all("SELECT id,name,type,created_at,updated_at,current_version FROM profiles ORDER BY created_at")

    def get(self, pid: str, version: int | None = None) -> dict | None:
        p = self.db.one("SELECT * FROM profiles WHERE id=?", (pid,))
        if not p:
            return None
        v = self.db.one("SELECT * FROM profile_versions WHERE profile_id=? AND version=?", (pid, version or p["current_version"]))
        return {**p, "version": v["version"], "version_id": v["id"], "config": json.loads(v["config_json"]), "note": v["note"]}

    def save(self, pid: str, config: dict, note: str = "saved") -> dict:
        p = self.db.one("SELECT * FROM profiles WHERE id=?", (pid,))
        if not p:
            raise KeyError(pid)
        cfg = normalize(config)
        ver = p["current_version"] + 1
        t = now()
        self.db.execute("INSERT INTO profile_versions(profile_id,version,config_json,note,created_at) VALUES(?,?,?,?,?)",
                        (pid, ver, dumps(cfg), note, t))
        self.db.execute("UPDATE profiles SET name=?, type=?, current_version=?, updated_at=? WHERE id=?",
                        (cfg["name"] or p["name"], cfg["type"], ver, t, pid))
        return self.get(pid)

    def versions(self, pid: str) -> list[dict]:
        return self.db.all("SELECT id,version,note,created_at FROM profile_versions WHERE profile_id=? ORDER BY version DESC", (pid,))

    def rollback(self, pid: str, version: int) -> dict:
        old = self.get(pid, version)
        if not old:
            raise KeyError(f"{pid}@{version}")
        return self.save(pid, old["config"], note=f"rollback to v{version}")

    def delete(self, pid: str) -> None:
        self.db.execute("DELETE FROM profile_versions WHERE profile_id=?", (pid,))
        self.db.execute("DELETE FROM profiles WHERE id=?", (pid,))

    def resolve(self, pid: str | None) -> tuple[dict, int | None]:
        p = self.get(pid) if pid else None
        if not p:
            first = self.db.one("SELECT id FROM profiles ORDER BY created_at LIMIT 1")
            p = self.get(first["id"]) if first else None
        if not p:
            cfg = preset("bank_support")
            return {"_id": None, "config": cfg}, None
        return {"_id": p["id"], "config": p["config"]}, p["version_id"]

    @staticmethod
    def presets() -> dict:
        return {k: preset(k) for k in PRESETS}
