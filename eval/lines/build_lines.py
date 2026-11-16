"""Source of truth for the M0 test lines. Run to regenerate test_lines.jsonl.

Numbers are written as words (that is how they are spoken; WER references must match speech).
All lines are DRAFTS by Claude and need native-speaker review before recording
(column `reviewed` stays false until a native speaker signs off in eval/lines/REVIEW.md).
"""
import json
import pathlib

TOPICS = ["balance", "card_block", "branch_hours", "tour_booking", "fd_rate",
          "account_number", "double_charge", "cruise_food", "transfer", "human_agent"]

MONO = {
    "en": [
        "Hi, I'd like to check the balance on my savings account.",
        "My debit card was stolen yesterday, please block it right away.",
        "What time does your branch open on Saturday?",
        "I want to book a two day tour of the old city for my family.",
        "Can you tell me the interest rate on a fixed deposit?",
        "My account number ends in four seven two nine.",
        "I was charged twice for the same hotel booking.",
        "Is there a vegetarian option on the evening river cruise?",
        "Please transfer five thousand rupees to my sister's account.",
        "Can I speak to a human agent, please?",
    ],
    "ja": [
        "こんにちは、普通預金の残高を確認したいのですが。",
        "昨日キャッシュカードを盗まれたので、すぐに止めてください。",
        "土曜日は支店が何時に開きますか。",
        "家族で旧市街の二日間のツアーを予約したいです。",
        "定期預金の金利を教えていただけますか。",
        "口座番号の下四桁は四七二九です。",
        "同じホテルの予約で二回請求されています。",
        "夕方のリバークルーズにベジタリアン向けの食事はありますか。",
        "妹の口座に五千ルピーを振り込んでください。",
        "担当者の方と直接話せますか。",
    ],
    "hi": [
        "नमस्ते, मुझे अपने बचत खाते का बैलेंस जानना है।",
        "कल मेरा डेबिट कार्ड चोरी हो गया, कृपया उसे तुरंत ब्लॉक कर दीजिए।",
        "शनिवार को आपकी शाखा कितने बजे खुलती है?",
        "मैं अपने परिवार के लिए पुराने शहर का दो दिन का टूर बुक करना चाहता हूँ।",
        "क्या आप मुझे फिक्स्ड डिपॉज़िट की ब्याज दर बता सकते हैं?",
        "मेरे खाते का नंबर चार सात दो नौ पर खत्म होता है।",
        "एक ही होटल बुकिंग के लिए मुझसे दो बार पैसे काटे गए हैं।",
        "क्या शाम की नदी क्रूज़ में शाकाहारी खाना मिलता है?",
        "कृपया मेरी बहन के खाते में पाँच हज़ार रुपये भेज दीजिए।",
        "क्या मैं किसी इंसान से बात कर सकता हूँ?",
    ],
    "bn": [
        "নমস্কার, আমি আমার সেভিংস অ্যাকাউন্টের ব্যালেন্স জানতে চাই।",
        "গতকাল আমার ডেবিট কার্ড চুরি হয়ে গেছে, দয়া করে এখনই ব্লক করে দিন।",
        "শনিবার আপনাদের শাখা কটায় খোলে?",
        "আমি আমার পরিবারের জন্য পুরনো শহরের দুই দিনের একটা ট্যুর বুক করতে চাই।",
        "ফিক্সড ডিপোজিটের সুদের হার কত, বলতে পারবেন?",
        "আমার অ্যাকাউন্ট নম্বরের শেষ চারটে সংখ্যা চার সাত দুই নয়।",
        "একই হোটেল বুকিংয়ের জন্য আমার কাছ থেকে দুবার টাকা কাটা হয়েছে।",
        "সন্ধ্যার নদী ক্রুজে কি নিরামিষ খাবার পাওয়া যায়?",
        "দয়া করে আমার বোনের অ্যাকাউন্টে পাঁচ হাজার টাকা পাঠিয়ে দিন।",
        "আমি কি একজন মানুষের সাথে কথা বলতে পারি?",
    ],
    "kn": [
        "ನಮಸ್ಕಾರ, ನನ್ನ ಉಳಿತಾಯ ಖಾತೆಯ ಬ್ಯಾಲೆನ್ಸ್ ತಿಳಿಯಬೇಕು.",
        "ನಿನ್ನೆ ನನ್ನ ಡೆಬಿಟ್ ಕಾರ್ಡ್ ಕಳುವಾಗಿದೆ, ದಯವಿಟ್ಟು ತಕ್ಷಣ ಬ್ಲಾಕ್ ಮಾಡಿ.",
        "ಶನಿವಾರ ನಿಮ್ಮ ಶಾಖೆ ಎಷ್ಟು ಗಂಟೆಗೆ ತೆರೆಯುತ್ತದೆ?",
        "ನನ್ನ ಕುಟುಂಬಕ್ಕಾಗಿ ಹಳೆಯ ನಗರದ ಎರಡು ದಿನಗಳ ಪ್ರವಾಸ ಬುಕ್ ಮಾಡಬೇಕು.",
        "ಸ್ಥಿರ ಠೇವಣಿಯ ಬಡ್ಡಿ ದರ ಎಷ್ಟು ಎಂದು ಹೇಳಬಹುದೇ?",
        "ನನ್ನ ಖಾತೆ ಸಂಖ್ಯೆ ನಾಲ್ಕು ಏಳು ಎರಡು ಒಂಬತ್ತು ಎಂದು ಕೊನೆಗೊಳ್ಳುತ್ತದೆ.",
        "ಒಂದೇ ಹೋಟೆಲ್ ಬುಕಿಂಗ್‌ಗೆ ನನ್ನಿಂದ ಎರಡು ಬಾರಿ ಹಣ ಕಡಿತವಾಗಿದೆ.",
        "ಸಂಜೆಯ ನದಿ ಕ್ರೂಸ್‌ನಲ್ಲಿ ಸಸ್ಯಾಹಾರಿ ಊಟ ಸಿಗುತ್ತದೆಯೇ?",
        "ದಯವಿಟ್ಟು ನನ್ನ ತಂಗಿಯ ಖಾತೆಗೆ ಐದು ಸಾವಿರ ರೂಪಾಯಿ ಕಳುಹಿಸಿ.",
        "ನಾನು ಯಾರಾದರೂ ಸಿಬ್ಬಂದಿಯೊಂದಿಗೆ ಮಾತನಾಡಬಹುದೇ?",
    ],
}

# Mixed / code-switched / romanized lines. `lang` = expected dominant (reply) language,
# `accept` = languages also counted correct when the dominant one is genuinely ambiguous.
MIXED = [
    ("hi", ["hi"], "मेरे credit card का payment due date कब है?", "hinglish", "card_block"),
    ("hi", ["hi"], "Mera account balance kitna hai, please bata dijiye.", "romanized_hi", "balance"),
    ("hi", ["hi"], "मुझे loan EMI के बारे में information चाहिए।", "hinglish", "loan"),
    ("bn", ["bn"], "আমার booking টা cancel করতে চাই, refund কবে পাব?", "banglish", "double_charge"),
    ("bn", ["bn"], "Amar card ta block kore din please.", "romanized_bn", "card_block"),
    ("kn", ["kn"], "ನನ್ನ flight ticket booking confirm ಆಗಿದೆಯಾ?", "kanglish", "tour_booking"),
    ("kn", ["kn", "en"], "Please ನನ್ನ card block ಮಾಡಿ, it's urgent.", "kanglish", "card_block"),
    ("ja", ["ja"], "来週のフライトの booking を change したいです。", "ja_en", "tour_booking"),
    ("en", ["en"], "I need help with my Aadhaar linked account, jaldi please.", "en_hi", "balance"),
    ("en", ["en"], "Can you book a ryokan in Kyoto for two nights?", "en_ja", "tour_booking"),
]


def main():
    out = pathlib.Path(__file__).with_name("test_lines.jsonl")
    rows = []
    for lang, lines in MONO.items():
        for i, text in enumerate(lines, 1):
            rows.append({"id": f"{lang}_{i:02d}", "lang": lang, "accept": [lang], "text": text,
                         "category": "mono", "topic": TOPICS[i - 1],
                         "numbers": TOPICS[i - 1] in ("account_number", "transfer"),
                         "romanized": False, "reviewed": False})
    for i, (lang, accept, text, cat, topic) in enumerate(MIXED, 1):
        rows.append({"id": f"mx_{i:02d}", "lang": lang, "accept": accept, "text": text,
                     "category": cat, "topic": topic, "numbers": False,
                     "romanized": cat.startswith("romanized"), "reviewed": False})
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} lines to {out}")


if __name__ == "__main__":
    main()
