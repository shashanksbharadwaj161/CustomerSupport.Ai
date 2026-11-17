"""SCRIPTED demo provider (SHAON_LLM_PROVIDER=scripted): NOT Claude, NOT a language model.

For recordings and tests on a machine without an Anthropic key. It recognises a few customer intents in the caller's
transcript (keywords per language) and answers with fixed, native-script replies grounded in the FAKE Lotus Bay Bank
demo site (eval/fixtures/sites/lotus-bank: hours, cards, contact). Every reply is labelled `model="scripted"` and the UI
shows "scripted test replies". Lines are machine-written; native-speaker review PENDING.
"""
from __future__ import annotations

import unicodedata

from agent.llm.provider import LLMProvider, LLMResult, _emit, _lang_from_messages

INTENTS = {
    "hours": {"en": ["saturday", "open", "hours", "time"], "hi": ["शनिवार", "खुल", "समय", "बजे"],
              "bn": ["শনিবার", "খোল", "সময়", "কটায়"], "kn": ["ಶನಿವಾರ", "ತೆರೆ", "ಸಮಯ", "ಗಂಟೆ"],
              "ja": ["土曜", "何時", "開", "営業"]},
    "card": {"en": ["card", "lost", "block", "stolen"], "hi": ["कार्ड", "खो", "ब्लॉक"],
             "bn": ["কার্ড", "হারি", "ব্লক"], "kn": ["ಕಾರ್ಡ್", "ಕಳೆದ", "ಬ್ಲಾಕ್"],
             "ja": ["カード", "紛失", "なくし", "止め", "停止"]},
    "human": {"en": ["human", "person", "agent", "someone"], "hi": ["इंसान", "व्यक्ति", "किसी से बात"],
              "bn": ["মানুষ", "কারও সাথে"], "kn": ["ಮನುಷ್ಯ", "ವ್ಯಕ್ತಿ"], "ja": ["人と", "担当者", "オペレーター"]},
}
REPLIES = {
    "hours": {
        "en": "On Saturday our branch is open from ten in the morning to one in the afternoon.",
        "hi": "शनिवार को हमारी शाखा सुबह दस बजे से दोपहर एक बजे तक खुली रहती है।",
        "bn": "শনিবার আমাদের শাখা সকাল দশটা থেকে দুপুর একটা পর্যন্ত খোলা থাকে।",
        "kn": "ಶನಿವಾರ ನಮ್ಮ ಶಾಖೆ ಬೆಳಿಗ್ಗೆ ಹತ್ತು ಗಂಟೆಯಿಂದ ಮಧ್ಯಾಹ್ನ ಒಂದು ಗಂಟೆಯವರೆಗೆ ತೆರೆದಿರುತ್ತದೆ.",
        "ja": "土曜日は午前十時から午後一時まで営業しております。",
    },
    "card": {
        "en": "We block a lost card right after we verify your registered phone number, and a new card arrives in five to seven working days.",
        "hi": "पंजीकृत फ़ोन नंबर की पुष्टि के तुरंत बाद हम कार्ड ब्लॉक कर देते हैं, और नया कार्ड पाँच से सात कार्य दिवसों में पहुँच जाता है।",
        "bn": "নিবন্ধিত ফোন নম্বর যাচাই করার পরেই আমরা কার্ডটি ব্লক করে দিই, আর নতুন কার্ড পাঁচ থেকে সাত কার্যদিবসে পৌঁছে যায়।",
        "kn": "ನೋಂದಾಯಿತ ಫೋನ್ ಸಂಖ್ಯೆಯನ್ನು ಪರಿಶೀಲಿಸಿದ ತಕ್ಷಣ ನಾವು ಕಾರ್ಡ್ ಬ್ಲಾಕ್ ಮಾಡುತ್ತೇವೆ, ಹೊಸ ಕಾರ್ಡ್ ಐದರಿಂದ ಏಳು ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ತಲುಪುತ್ತದೆ.",
        "ja": "ご登録の電話番号を確認後すぐにカードを停止し、新しいカードは五から七営業日でお届けします。",
    },
    "human": {
        "en": "Of course. Our human colleagues are available Monday to Saturday, nine in the morning to seven in the evening; I will connect you.",
        "hi": "ज़रूर। हमारे सहकर्मी सोमवार से शनिवार सुबह नौ से शाम सात बजे तक उपलब्ध हैं; मैं आपको जोड़ती हूँ।",
        "bn": "অবশ্যই। আমাদের সহকর্মীরা সোমবার থেকে শনিবার সকাল নটা থেকে সন্ধ্যা সাতটা পর্যন্ত আছেন; আমি আপনাকে যুক্ত করছি।",
        "kn": "ಖಂಡಿತ. ನಮ್ಮ ಸಹೋದ್ಯೋಗಿಗಳು ಸೋಮವಾರದಿಂದ ಶನಿವಾರದವರೆಗೆ ಬೆಳಿಗ್ಗೆ ಒಂಬತ್ತರಿಂದ ಸಂಜೆ ಏಳರವರೆಗೆ ಲಭ್ಯವಿದ್ದಾರೆ; ನಾನು ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತೇನೆ.",
        "ja": "かしこまりました。担当者は月曜日から土曜日の午前九時から午後七時まで対応しております。おつなぎいたします。",
    },
    "unknown": {
        "en": "Sorry, I did not catch that. Could you say it again, please?",
        "hi": "माफ़ कीजिए, मैं ठीक से सुन नहीं पाई। क्या आप दोबारा कह सकते हैं?",
        "bn": "দুঃখিত, আমি ঠিক বুঝতে পারিনি। আপনি কি আবার বলবেন?",
        "kn": "ಕ್ಷಮಿಸಿ, ನನಗೆ ಸರಿಯಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳುತ್ತೀರಾ?",
        "ja": "申し訳ございません、うまく聞き取れませんでした。もう一度お願いできますか。",
    },
}


# NOTE: never use short stems such as "कार"/"কার"/"ಕಾರ" for "card": they are inside नमस्कार/নমস্কার/ನಮಸ್ಕಾರ ("hello")
# and turned every greeting into a lost-card question (caught in the Bengali recording, 2026-11-17).
def intent_of(text: str, lang: str) -> str:
    t = unicodedata.normalize("NFC", text).lower()
    scores = {k: sum(w.lower() in t for w in v.get(lang, []) + v["en"]) for k, v in INTENTS.items()}
    if scores["card"] and scores["card"] >= scores["hours"]:  # "lost card" outranks the generic "time" word
        return "card"
    best = max(scores, key=scores.get)
    return best if scores[best] else "unknown"


class ScriptedDemoProvider(LLMProvider):
    name = "scripted"
    is_real = False

    async def stream(self, *, system, messages, model=None, max_tokens=300, tools=None, on_text=None,
                     purpose="reply", call_id=None) -> LLMResult:
        lang, caller = _lang_from_messages(messages)
        lang = lang if lang in REPLIES["hours"] else "en"
        text = REPLIES[intent_of(caller, lang)][lang]
        await _emit(text, on_text)
        return LLMResult(text=text, model="scripted", stop_reason="end_turn", ttft_ms=0, total_ms=0)

    async def complete_json(self, **kw) -> dict:
        raise ValueError("scripted demo provider: no model checks")
