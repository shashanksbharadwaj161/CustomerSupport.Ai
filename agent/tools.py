"""Mock tools per agent type (FAKE DATA ONLY). Layer 3 guardrail: only tools in the profile's
allowlist (agent.presets.TOOLS_BY_TYPE) are ever offered to the model or executed."""
from __future__ import annotations

import hashlib

TOOL_SPECS = {
    "balance_lookup": {
        "name": "balance_lookup",
        "description": "Look up the caller's own account balance in the FAKE demo bank. Requires the last four digits of the account and of the registered phone number.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["account_last4", "phone_last4"],
                         "properties": {"account_last4": {"type": "string"}, "phone_last4": {"type": "string"}}},
    },
    "card_block_request": {
        "name": "card_block_request",
        "description": "File a request to block the caller's lost or stolen card in the FAKE demo bank.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["card_last4"],
                         "properties": {"card_last4": {"type": "string"}}},
    },
    "itinerary_search": {
        "name": "itinerary_search",
        "description": "Search the FAKE tour catalog by destination and number of days.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["destination"],
                         "properties": {"destination": {"type": "string"}, "days": {"type": "integer"}}},
    },
    "order_lookup": {
        "name": "order_lookup",
        "description": "Look up a FAKE demo order by order id.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["order_id"],
                         "properties": {"order_id": {"type": "string"}}},
    },
    "appointment_slots": {
        "name": "appointment_slots",
        "description": "List FAKE free appointment slots for a weekday.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["weekday"],
                         "properties": {"weekday": {"type": "string"}}},
    },
}

_TOURS = [
    {"name": "Old city heritage tour", "destination": "old city", "days": 2, "price_inr": 8000},
    {"name": "Evening river cruise", "destination": "river", "days": 1, "price_inr": 2500},
    {"name": "Kyoto temples and ryokan", "destination": "kyoto", "days": 3, "price_inr": 65000},
]


def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def run_tool(name: str, args: dict, allowed: list[str]) -> dict:
    if name not in allowed:
        return {"error": f"tool '{name}' is not allowed for this agent", "blocked": True}
    if name == "balance_lookup":
        a, p = str(args.get("account_last4", "")), str(args.get("phone_last4", ""))
        if not (a.isdigit() and len(a) == 4 and p.isdigit() and len(p) == 4):
            return {"error": "verification failed: need four digits for account and phone"}
        return {"fake_data": True, "account_last4": a, "balance_inr": 1000 + _h(a + p) % 90000, "currency": "INR"}
    if name == "card_block_request":
        c = str(args.get("card_last4", ""))
        if not (c.isdigit() and len(c) == 4):
            return {"error": "need the last four digits of the card"}
        return {"fake_data": True, "status": "blocked", "card_last4": c, "reference": f"BLK{_h(c) % 100000:05d}",
                "replacement_days": "five to seven working days"}
    if name == "itinerary_search":
        d = str(args.get("destination", "")).lower()
        hits = [t for t in _TOURS if d and (d in t["destination"] or t["destination"] in d)] or _TOURS[:1]
        return {"fake_data": True, "results": hits}
    if name == "order_lookup":
        oid = str(args.get("order_id", ""))
        return {"fake_data": True, "order_id": oid, "status": ["packed", "shipped", "delivered"][_h(oid) % 3]}
    if name == "appointment_slots":
        return {"fake_data": True, "weekday": args.get("weekday"), "slots": ["ten in the morning", "two thirty in the afternoon"]}
    return {"error": "unknown tool"}


def specs_for(allowed: list[str]) -> list[dict]:
    return [TOOL_SPECS[t] for t in allowed if t in TOOL_SPECS]
