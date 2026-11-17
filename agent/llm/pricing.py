"""USD per million tokens (Anthropic first-party list prices, cached 2026-11-03).
Re-check https://www.anthropic.com/pricing before relying on totals. Spend is tracked
from response.usage; the DB-backed cap (M1) uses the same table.
Haiku 5.5 price applies to prompts up to 100K tokens (higher beyond; our prompts are far below).
"""
from __future__ import annotations

from agent.llm.models import CATALOG, price as _price

PRICES = {m["id"]: {"in": m["in"], "out": m["out"]} for m in CATALOG}
CACHE_WRITE_MULT = 1.25  # 5-minute TTL
CACHE_READ_MULT = 0.10


def cost_usd(model: str, usage) -> float:
    p, _estimated = _price(model)  # unknown model: highest known rate (the cap can only stop early)
    get = (lambda k: getattr(usage, k, 0) or 0) if not isinstance(usage, dict) else (lambda k: usage.get(k, 0) or 0)
    inp = get("input_tokens")
    cw = get("cache_creation_input_tokens")
    cr = get("cache_read_input_tokens")
    out = get("output_tokens")
    return (inp * p["in"] + cw * p["in"] * CACHE_WRITE_MULT + cr * p["in"] * CACHE_READ_MULT
            + out * p["out"]) / 1_000_000
