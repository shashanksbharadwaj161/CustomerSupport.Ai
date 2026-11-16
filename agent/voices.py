"""Voice catalog: bakeoff_voices.json + catalog.json + user-added voices (DB). Personas map to a voice per language."""
from __future__ import annotations

import json
import pathlib

from agent.tts.base import Voice

VOICES_DIR = pathlib.Path(__file__).resolve().parent.parent / "voices"


def _load(name: str) -> dict:
    return json.loads((VOICES_DIR / name).read_text(encoding="utf-8"))


class VoiceCatalog:
    def __init__(self, extra: list[dict] | None = None):
        bake, cat = _load("bakeoff_voices.json"), _load("catalog.json")
        self.ref_text = bake["ref_text"]
        self.persona_sets: dict[str, dict[str, str]] = cat["persona_sets"]
        tags = cat.get("persona_tags", {})
        self.raw: dict[str, dict] = {}
        for v in bake["voices"] + cat["voices"] + (extra or []):
            v = dict(v)
            v.setdefault("persona_tag", tags.get(v["id"]))
            self.raw[v["id"]] = v

    def voice(self, vid: str) -> Voice | None:
        v = self.raw.get(vid)
        if not v:
            return None
        params = dict(v.get("params", {}))
        if v.get("reference_path"):
            params["ref_audio"] = v["reference_path"]
            params["ref_text"] = v.get("reference_text")
        return Voice(id=v["id"], language=v["language"], engine=v["engine"], display_name=v["display_name"],
                     license=v["license"], demo_only=bool(v.get("demo_only")), params=params)

    def list(self, lang: str | None = None) -> list[dict]:
        return [v for v in self.raw.values() if not lang or v["language"] == lang]

    def for_persona(self, persona: str, lang: str) -> str | None:
        return self.persona_sets.get(persona, {}).get(lang)
