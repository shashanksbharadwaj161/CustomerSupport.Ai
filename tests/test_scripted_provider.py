"""The SCRIPTED test provider must answer the question that was asked (recordings depend on it)."""
import pytest

from agent.llm.scripted import intent_of

CASES = [  # (language, recognised customer text as MMS/Whisper actually produced it in the recordings, intent)
    ("bn", "নমস্কার শনিবার আপনাদের সাখা কড়ায় খলে", "hours"),
    ("bn", "ধন্যবাদ আমার ডেভিড কার্ড হারিয়ে গেছে কার্টা ব্লক করতে পারবেন", "card"),
    ("hi", "नमस्ते शनीवार को आपकी शाखा कितने बजे खुलती है", "hours"),
    ("hi", "धन्यवाद मेरा डेविट कार्न खो गया है क्या आप उसे ब्लॉक कर सकती हैं", "card"),
    ("kn", "ನಮಸ್ಕಾರ ಶನಿವಾರ ನಿಮ್ಮ ಶಾಖೆ ಎಷ್ಟು ಗಂಟೆಗೆ ತೆರೆಯುತ್ತದೆ", "hours"),
    ("kn", "ಧನ್ಯವಾದ ನನ್ನ ಡೇವಿಡ್ ಕಾರ್ಡ್ ಕಳೆದುಹೋಗಿದೆ ಅದನ್ನು ಬ್ಲಾಕ್ ಮಾಡಬಹುದೆ", "card"),
    ("ja", "すみません土曜日は何時に開きますか", "hours"),
    ("ja", "ありがとうございます。デビットカードをなくしてしまいました。止めていただけますか。", "card"),
    ("en", "Hi, what time does your branch open on Saturday?", "hours"),
    ("en", "Thanks, I also lost my debit card. Can you block it?", "card"),
    ("bn", "নমস্কার", "unknown"),
]


@pytest.mark.parametrize("lang,text,want", CASES)
def test_intent(lang, text, want):
    assert intent_of(text, lang) == want
