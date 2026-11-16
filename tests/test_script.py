from agent.lang.script import count_scripts, dominant_language, find_digits, is_native_script


def test_each_script_detected():
    cases = {
        "en": "Please block my card.",
        "ja": "カードを止めてください。",
        "hi": "कृपया मेरा कार्ड ब्लॉक कर दीजिए।",
        "bn": "দয়া করে আমার কার্ড ব্লক করে দিন।",
        "kn": "ದಯವಿಟ್ಟು ನನ್ನ ಕಾರ್ಡ್ ಬ್ಲಾಕ್ ಮಾಡಿ.",
    }
    for lang, text in cases.items():
        assert dominant_language(text)[0] == lang, lang
        assert is_native_script(text, lang)


def test_kanji_only_is_japanese():
    assert dominant_language("口座番号")[0] == "ja"


def test_hinglish_in_devanagari_resolves_to_hindi():
    assert dominant_language("मेरे credit card का payment due date कब है?")[0] == "hi"


def test_romanized_hindi_is_not_native():
    assert not is_native_script("Mera account balance kitna hai", "hi")


def test_digits_in_all_scripts():
    assert find_digits("pay 500") == ["5", "0", "0"]
    assert find_digits("५००") and find_digits("৫০০") and find_digits("೫೦೦") and find_digits("５")
    assert find_digits("पाँच सौ") == []


def test_indic_digits_are_not_letters():
    assert count_scripts("५००")["hi"] == 0


def test_empty():
    assert dominant_language("") == (None, 0.0)
    assert dominant_language("123 !!") == (None, 0.0)
