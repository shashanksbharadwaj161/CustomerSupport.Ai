"""Spend ledger and cap, stored in SQLite so restarts do not reset them."""
from __future__ import annotations

from api.db import DB, now
from agent.llm.pricing import cost_usd


class SpendCapReached(RuntimeError):
    pass


class Spend:
    def __init__(self, db: DB, default_cap: float):
        self.db = db
        self.default_cap = default_cap

    @property
    def cap(self) -> float:
        r = self.db.one("SELECT value FROM settings WHERE key='spend_cap_usd'")
        return float(r["value"]) if r else self.default_cap

    def set_cap(self, usd: float) -> None:
        if usd < 0:
            raise ValueError("cap must be >= 0")
        self.db.execute("INSERT INTO settings(key,value,encrypted,updated_at) VALUES('spend_cap_usd',?,0,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at", (str(usd), now()))

    @property
    def spent(self) -> float:
        r = self.db.one("SELECT COALESCE(SUM(usd),0) AS s FROM spend")
        return float(r["s"])

    def check(self) -> None:
        if self.spent >= self.cap:
            raise SpendCapReached(f"spend cap ${self.cap:.2f} reached (spent ${self.spent:.4f})")

    def record(self, model: str, usage: dict, purpose: str, call_id: str | None = None) -> float:
        usd = cost_usd(model, usage) if model in _known() else 0.0
        self.db.execute(
            "INSERT INTO spend(call_id,purpose,model,input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,usd,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (call_id, purpose, model, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
             usage.get("cache_read_input_tokens", 0), usage.get("cache_creation_input_tokens", 0), usd, now()))
        return usd

    def summary(self) -> dict:
        rows = self.db.all("SELECT purpose, COUNT(*) n, SUM(usd) usd FROM spend GROUP BY purpose")
        return {"cap_usd": self.cap, "spent_usd": round(self.spent, 6), "by_purpose": rows}


def _known():
    from agent.llm.pricing import PRICES
    return PRICES
