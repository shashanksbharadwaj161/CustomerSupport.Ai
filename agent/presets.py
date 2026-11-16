"""Agent presets (PLAN.md section 7). A profile is ONE JSON document, versioned on every save.

All demo businesses and data are fictional. Greetings always disclose that the caller is
talking to an AI assistant (CLAUDE.md: first line of every call).
"""
from __future__ import annotations

import copy

LANGS = ["en", "ja", "hi", "bn", "kn"]

AI_DISCLOSURE = {  # used to verify / prefix greetings
    "en": "AI assistant", "ja": "AIアシスタント", "hi": "एआई सहायक", "bn": "এআই সহকারী", "kn": "ಎಐ ಸಹಾಯಕ",
}

HANDOFF = {
    "en": "I will connect you to a human colleague now. Please stay on the line.",
    "ja": "これから担当者におつなぎします。少々お待ちください。",
    "hi": "मैं अब आपको हमारे एक सहकर्मी से जोड़ रही हूँ। कृपया लाइन पर बने रहें।",
    "bn": "আমি এখন আপনাকে আমাদের একজন সহকর্মীর সাথে যুক্ত করছি। দয়া করে লাইনে থাকুন।",
    "kn": "ನಾನು ಈಗ ನಿಮ್ಮನ್ನು ನಮ್ಮ ಸಹೋದ್ಯೋಗಿಯೊಂದಿಗೆ ಸಂಪರ್ಕಿಸುತ್ತೇನೆ. ದಯವಿಟ್ಟು ಲೈನ್‌ನಲ್ಲಿರಿ.",
}

TOOLS_BY_TYPE = {
    "bank_support": ["balance_lookup", "card_block_request"],
    "tourism": ["itinerary_search"],
    "ecommerce": ["order_lookup"],
    "clinic_frontdesk": ["appointment_slots"],
    "custom": [],
}


def _greeting(org: str, name: str) -> dict:
    return {
        "en": f"Hello, this is {name}, the AI assistant for {org}. How can I help you today?",
        "ja": f"お電話ありがとうございます。{org}のAIアシスタント、{name}です。ご用件をお聞かせください。",
        "hi": f"नमस्ते, मैं {name} हूँ, {org} की एआई सहायक। मैं आपकी क्या मदद कर सकती हूँ?",
        "bn": f"নমস্কার, আমি {name}, {org}-এর এআই সহকারী। আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
        "kn": f"ನಮಸ್ಕಾರ, ನಾನು {name}, {org}ನ ಎಐ ಸಹಾಯಕ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
    }


BASE = {
    "name": "", "type": "custom", "custom_role_text": "",
    "persona": {"name": "Asha", "tone": "warm, calm, concise", "formality": "formal",
                "greeting": {}, "closing": {},
                "politeness": {"ja": "teineigo (desu/masu), sonkeigo for the caller's actions",
                               "hi": "formal aap", "bn": "formal apni", "kn": "formal neevu"}},
    "response_style": {"max_sentences": 2, "verbosity": "short", "confirm_numbers": True, "fillers": False,
                       "readback_rules": "Read back IDs, phone numbers and amounts to confirm. Never read a full card or account number: only the last four digits."},
    "languages": {"enabled": list(LANGS), "default": "en", "auto_switch": True, "llm_model_override": {}},
    "guardrails": {"allowed_topics": [], "forbidden_topics": [], "required_disclaimers": [],
                   "pii_rules": "Never ask for or repeat full card numbers, PINs, passwords or OTPs.",
                   "escalation_triggers": ["caller asks for a human", "complaint about fraud", "medical emergency"],
                   "handoff_message": dict(HANDOFF), "refusal_style": "polite, brief, offer a human",
                   "banned_claims": [], "reply_check": "combined", "input_check": "local"},
    "voices": {"persona_set": "warm_female", "by_language": {}},
    "knowledge": {"source_ids": [], "top_k": 4, "min_score": 0.35, "site_brief": True},
    "tools": [],
}

PRESETS = {
    "bank_support": {
        "name": "Lotus Bay Bank support", "type": "bank_support",
        "persona": {"name": "Asha", "greeting": _greeting("Lotus Bay Bank", "Asha")},
        "guardrails": {
            "allowed_topics": ["accounts", "cards", "branch hours", "fixed deposits", "transfers (how to)", "disputes"],
            "forbidden_topics": ["investment advice", "stock tips", "other customers' accounts", "loan approval promises"],
            "required_disclaimers": [{"trigger": "interest rate", "text": "Rates can change; please check the latest rate before you invest."}],
            "banned_claims": ["guaranteed returns", "guaranteed approval", "risk-free"],
        },
    },
    "tourism": {
        "name": "Lotus Bay Travel desk", "type": "tourism",
        "persona": {"name": "Mira", "tone": "friendly, upbeat, concise", "greeting": _greeting("Lotus Bay Travel", "Mira")},
        "guardrails": {
            "allowed_topics": ["tours", "cruises", "bookings", "visa help", "airport pickup"],
            "forbidden_topics": ["medical advice", "immigration legal advice"],
            "required_disclaimers": [{"trigger": "visa", "text": "Visa decisions are made by the embassy, not by us."}],
            "banned_claims": ["guaranteed visa", "100 percent refund always"],
        },
    },
    "ecommerce": {
        "name": "Lotus Bay Store help", "type": "ecommerce",
        "persona": {"name": "Ria", "greeting": _greeting("Lotus Bay Store", "Ria")},
        "guardrails": {"allowed_topics": ["orders", "delivery", "returns", "refunds"],
                       "forbidden_topics": ["other customers' orders"], "banned_claims": ["free forever"]},
    },
    "clinic_frontdesk": {
        "name": "Lotus Bay Clinic front desk", "type": "clinic_frontdesk",
        "persona": {"name": "Nila", "greeting": _greeting("Lotus Bay Clinic", "Nila")},
        "guardrails": {"allowed_topics": ["appointments", "clinic hours", "directions"],
                       "forbidden_topics": ["diagnosis", "medication dosage", "medical advice"],
                       "required_disclaimers": [{"trigger": "emergency", "text": "If this is an emergency, call your local emergency number now."}],
                       "escalation_triggers": ["medical emergency", "chest pain", "breathing difficulty"],
                       "banned_claims": ["cure", "guaranteed recovery"]},
    },
    "custom": {"name": "Custom agent", "type": "custom",
               "custom_role_text": "You answer questions about the business described in the site brief.",
               "persona": {"greeting": _greeting("our team", "Asha")}},
}


def deep_merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def preset(kind: str) -> dict:
    if kind not in PRESETS:
        raise KeyError(kind)
    p = deep_merge(BASE, PRESETS[kind])
    p["tools"] = list(TOOLS_BY_TYPE[kind])
    p["persona"].setdefault("greeting", _greeting("our team", p["persona"]["name"]))
    return normalize(p)


def normalize(p: dict) -> dict:
    """Fill defaults and enforce invariants (AI disclosure in every greeting, handoff per language)."""
    p = deep_merge(BASE, p)
    g = p["persona"].get("greeting") or {}
    for lang in LANGS:
        text = g.get(lang) or _greeting("our team", p["persona"]["name"])[lang]
        if AI_DISCLOSURE[lang].lower() not in text.lower() and "ai" not in text.lower().split():
            text = _greeting("our team", p["persona"]["name"])[lang].split(".")[0] + ". " + text
        g[lang] = text
    p["persona"]["greeting"] = g
    hm = p["guardrails"].get("handoff_message") or {}
    p["guardrails"]["handoff_message"] = {lang: hm.get(lang) or HANDOFF[lang] for lang in LANGS}
    allowed_tools = TOOLS_BY_TYPE.get(p["type"], [])
    p["tools"] = [t for t in p.get("tools", []) if t in allowed_tools]  # layer 3: allowlist per type
    en = [l for l in p["languages"]["enabled"] if l in LANGS] or ["en"]
    p["languages"]["enabled"] = en
    if p["languages"]["default"] not in en:
        p["languages"]["default"] = en[0]
    p["response_style"]["max_sentences"] = max(1, min(4, int(p["response_style"].get("max_sentences", 2))))
    return p
