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

    def set_cap(self, usd: float, by_user: bool = True) -> None:
        if usd < 0 or usd != usd or usd > 100000:
            raise ValueError("cap must be between 0 and 100000")
        for k, v in (("spend_cap_usd", str(usd)), ("spend_cap_source", "user" if by_user else "system")):
            self.db.execute("INSERT INTO settings(key,value,encrypted,updated_at) VALUES(?,?,0,?) "
                            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at", (k, v, now()))
        self.db.execute("DELETE FROM settings WHERE key='spend_cap_notice'")

    @property
    def source(self) -> str:
        r = self.db.one("SELECT value FROM settings WHERE key='spend_cap_source'")
        if r:
            return r["value"]
        return "legacy" if self.db.one("SELECT value FROM settings WHERE key='spend_cap_usd'") else "default"

    def unlock_stale_zero_cap(self) -> bool:
        """Local preview: a 0 cap that the USER never chose (written by an earlier launcher/preview) is reset to the
        default and a notice is shown. A cap the user set in Settings is never touched; the spend ledger never is."""
        r = self.db.one("SELECT value FROM settings WHERE key='spend_cap_usd'")
        if not r or float(r["value"]) > 0 or self.source == "user":
            return False
        self.db.execute("DELETE FROM settings WHERE key='spend_cap_usd'")
        self.db.execute("INSERT INTO settings(key,value,encrypted,updated_at) VALUES('spend_cap_notice',?,0,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                        (f"The spend cap was 0 (set by an earlier launcher, not by you), which blocked every Claude call. "
                         f"It is back to the default {self.default_cap:.2f} USD. Spend history is unchanged.", now()))
        return True

    @property
    def spent(self) -> float:
        r = self.db.one("SELECT COALESCE(SUM(usd),0) AS s FROM spend")
        return float(r["s"])

    def check(self) -> None:
        if self.spent >= self.cap:
            raise SpendCapReached(f"spend cap ${self.cap:.2f} reached (spent ${self.spent:.4f})")

    def record(self, model: str, usage: dict, purpose: str, call_id: str | None = None) -> float:
        usd = cost_usd(model, usage)  # unknown models are priced conservatively, never as free
        self.db.execute(
            "INSERT INTO spend(call_id,purpose,model,input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,usd,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (call_id, purpose, model, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
             usage.get("cache_read_input_tokens", 0), usage.get("cache_creation_input_tokens", 0), usd, now()))
        return usd

    def summary(self) -> dict:
        rows = self.db.all("SELECT purpose, COUNT(*) n, SUM(usd) usd FROM spend GROUP BY purpose")
        n = self.db.one("SELECT value FROM settings WHERE key='spend_cap_notice'")
        return {"cap_usd": self.cap, "spent_usd": round(self.spent, 6), "by_purpose": rows, "default_cap_usd": self.default_cap,
                "cap_source": self.source, "notice": n["value"] if n else None,
                "blocked": self.spent >= self.cap}


def _known():
    from agent.llm.pricing import PRICES
    return PRICES
