"""SQLite access (stdlib). One connection per call; WAL mode; schema created on first use."""
from __future__ import annotations

import json
import pathlib
import sqlite3
import threading
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, encrypted INTEGER DEFAULT 0, updated_at REAL);
CREATE TABLE IF NOT EXISTS spend (id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT, purpose TEXT, model TEXT,
  input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER, usd REAL, created_at REAL);
CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, name TEXT, type TEXT, created_at REAL, updated_at REAL, current_version INTEGER);
CREATE TABLE IF NOT EXISTS profile_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT, version INTEGER,
  config_json TEXT, note TEXT, created_at REAL, UNIQUE(profile_id, version));
CREATE TABLE IF NOT EXISTS knowledge_sources (id TEXT PRIMARY KEY, profile_id TEXT, url TEXT, status TEXT, pages INTEGER DEFAULT 0,
  chunks INTEGER DEFAULT 0, brief_text TEXT, brief_status TEXT, limits_json TEXT, error TEXT, embedder TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS knowledge_pages (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, url TEXT, title TEXT, depth INTEGER,
  rendered INTEGER, chars INTEGER, text TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS knowledge_events (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, kind TEXT, data_json TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS voices (id TEXT PRIMARY KEY, language TEXT, engine TEXT, display_name TEXT, persona_tag TEXT,
  reference_path TEXT, reference_text TEXT, params_json TEXT, license TEXT, demo_only INTEGER DEFAULT 0, source TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, profile_id TEXT, profile_version_id INTEGER, transport TEXT, started_at REAL,
  ended_at REAL, languages_used TEXT, provider TEXT, end_reason TEXT);
CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT, role TEXT, language TEXT, text TEXT,
  stt_ms INTEGER, llm_ms INTEGER, llm_ttft_ms INTEGER, guard_ms INTEGER, tts_ms INTEGER, first_audio_ms INTEGER,
  lang_reason TEXT, engine_json TEXT, sources_json TEXT, guardrail_json TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS guardrail_events (id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT, turn_id INTEGER, stage TEXT,
  verdict TEXT, rule TEXT, detail TEXT, created_at REAL);
CREATE INDEX IF NOT EXISTS turns_call ON turns(call_id);
CREATE INDEX IF NOT EXISTS kev_source ON knowledge_events(source_id);
"""


class DB:
    def __init__(self, path: pathlib.Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        with self._lock:
            c = sqlite3.connect(self.path, timeout=30)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            try:
                yield c
                c.commit()
            finally:
                c.close()

    def execute(self, sql: str, args: tuple | dict = ()) -> int:
        with self.conn() as c:
            cur = c.execute(sql, args)
            return cur.lastrowid

    def one(self, sql: str, args: tuple | dict = ()) -> dict | None:
        with self.conn() as c:
            r = c.execute(sql, args).fetchone()
            return dict(r) if r else None

    def all(self, sql: str, args: tuple | dict = ()) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]


def now() -> float:
    return time.time()


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True)
