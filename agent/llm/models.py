"""Claude model catalog for the Settings model selector.

Source: Anthropic's model overview / pricing (Claude API reference, cached 2026-11-03; re-check
https://platform.claude.com/docs/en/about-claude/models/overview and https://www.anthropic.com/pricing).
The LIVE list comes from the Models API (`client.models.list()`, free) when the user presses "Refresh models"
in Settings with a key configured; this table is the offline fallback and the price source for the spend cap.

Request parameters differ per model (a parameter one model needs is a 400 on another), so `request_params()`
picks the lowest-latency valid configuration for a voice turn:
- Haiku 5.5: thinking disabled (allowed at effort <= high), effort low.
- Sonnet 5.5: `thinking: {type: "disabled"}` is a 400 -> `{type: "between_tools"}` (thinking off; effort <= high).
- Opus 5.5 / Fable: thinking cannot be disabled -> omit it, effort low.
- Opus 5 / Sonnet 5 / Opus 4.8 / 4.7: thinking disabled accepted, effort low.
- Opus 4.6 / Sonnet 4.6: no thinking unless asked; effort low.
- Haiku 4.5: no `effort` (it errors there), no thinking.
- Unknown (explicit ID): only effort low; any 400 is shown in Settings as an honest error.
"""
from __future__ import annotations

import re

CATALOG_SOURCE = "Anthropic models overview + pricing, cached 2026-11-03"

# id, display name, tier note, input $/MTok, output $/MTok, context window
CATALOG: list[dict] = [
    {"id": "claude-haiku-5-5", "name": "Claude Haiku 5.5", "note": "fastest, lowest cost - recommended for live voice",
     "in": 0.10, "out": 0.50, "context": "1M", "family": "haiku-5"},
    {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5", "note": "stronger reasoning, still quick - good fallback",
     "in": 2.00, "out": 10.00, "context": "1M", "family": "sonnet-5-5"},
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5", "note": "most capable Opus; slower first word for voice",
     "in": 4.00, "out": 20.00, "context": "1M", "family": "opus-5-5"},
    {"id": "claude-sonnet-5", "name": "Claude Sonnet 5", "note": "previous Sonnet", "in": 2.00, "out": 10.00, "context": "1M", "family": "disable-ok"},
    {"id": "claude-opus-5", "name": "Claude Opus 5", "note": "previous Opus", "in": 5.00, "out": 25.00, "context": "1M", "family": "disable-ok"},
    {"id": "claude-fable-5-2", "name": "Claude Fable 5.2", "note": "most capable; highest cost, long turns", "in": 8.00, "out": 40.00,
     "context": "1M", "family": "fable"},
    {"id": "claude-opus-4-8", "name": "Claude Opus 4.8", "note": "older", "in": 5.00, "out": 25.00, "context": "1M", "family": "disable-ok"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "note": "older", "in": 3.00, "out": 15.00, "context": "1M", "family": "4-6"},
    {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "note": "older", "in": 1.00, "out": 5.00, "context": "200K", "family": "haiku-4-5"},
]
DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_FALLBACK = "claude-sonnet-5-5"
BY_ID = {m["id"]: m for m in CATALOG}
# unknown/explicit model IDs are charged at the most expensive known rate, so the spend cap can only stop early, never late
CONSERVATIVE = {"in": max(m["in"] for m in CATALOG), "out": max(m["out"] for m in CATALOG)}

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:@-]{2,79}$")


def valid_id_format(model: str) -> bool:
    return bool(_ID_RE.match(model or ""))


def family(model: str) -> str:
    if model in BY_ID:
        return BY_ID[model]["family"]
    if model.startswith("claude-fable") or model.startswith("claude-mythos"):
        return "fable"
    return "unknown"


def request_params(model: str, effort: str = "low") -> dict:
    """Extra Messages API params for a low-latency voice turn on `model` (see module docstring)."""
    f = family(model)
    if f == "haiku-4-5":
        return {}
    out: dict = {"output_config": {"effort": effort}}
    if f in ("haiku-5", "disable-ok"):
        out["thinking"] = {"type": "disabled"}
    elif f == "sonnet-5-5":
        out["thinking"] = {"type": "between_tools"}
    return out


def price(model: str) -> tuple[dict, bool]:
    """(prices per MTok, estimated?) - unknown models use the conservative (highest) known rate."""
    m = BY_ID.get(model)
    return ({"in": m["in"], "out": m["out"]}, False) if m else (CONSERVATIVE, True)


def merge_live(live: list[dict]) -> list[dict]:
    """Catalog entries enriched with what the Models API returned; live-only models appended (price: conservative)."""
    seen = {m["id"]: dict(m, live=False) for m in CATALOG}
    for m in live:
        mid = m.get("id")
        if not mid:
            continue
        row = seen.get(mid) or {"id": mid, "name": m.get("display_name") or mid, "note": "from your account's model list",
                                "in": None, "out": None, "context": None, "family": family(mid)}
        row.update(live=True, name=m.get("display_name") or row["name"],
                   max_input_tokens=m.get("max_input_tokens"), max_tokens=m.get("max_tokens"))
        seen[mid] = row
    return list(seen.values())
