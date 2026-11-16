"""Deterministic script detection from Unicode ranges.

Used for (CLAUDE.md, PLAN.md section 6):
- deciding the reply language from the reply text (never trusted from the model),
  at word level so code-mixed text resolves to its matrix language,
- flipping a language-ID guess when the transcript's script disagrees,
- checking replies are in native script (not romanized) and contain no digits.
"""
from __future__ import annotations

import unicodedata

LANGS = ("en", "ja", "hi", "bn", "kn")

# (start, end) inclusive code point ranges per language script.
_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "bn": ((0x0980, 0x09FF),),
    "hi": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),  # Devanagari + extended
    "kn": ((0x0C80, 0x0CFF),),
    "ja": (
        (0x3040, 0x309F),  # hiragana
        (0x30A0, 0x30FF),  # katakana (incl. long vowel mark)
        (0x31F0, 0x31FF),  # katakana phonetic extensions
        (0x3400, 0x4DBF),  # CJK ext A
        (0x4E00, 0x9FFF),  # CJK unified ideographs
        (0xFF66, 0xFF9F),  # halfwidth katakana
    ),
    "en": ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)),  # Latin letters
}

# Digits: ASCII, fullwidth, and native digit blocks. Replies must spell numbers as words.
_DIGIT_RANGES = (
    (0x0030, 0x0039),
    (0xFF10, 0xFF19),
    (0x0966, 0x096F),  # Devanagari
    (0x09E6, 0x09EF),  # Bengali
    (0x0CE6, 0x0CEF),  # Kannada
)


def _lang_of_char(ch: str) -> str | None:
    cp = ord(ch)
    for lang, ranges in _RANGES.items():
        for lo, hi in ranges:
            if lo <= cp <= hi:
                # Digits inside Indic blocks are not letters.
                if unicodedata.category(ch).startswith("N"):
                    return None
                return lang
    return None


def count_scripts(text: str) -> dict[str, int]:
    """Count letters per language script. Punctuation, digits and spaces are ignored."""
    counts = {lang: 0 for lang in LANGS}
    for ch in unicodedata.normalize("NFC", text):
        lang = _lang_of_char(ch)
        if lang:
            counts[lang] += 1
    return counts


NATIVE_MIN_WORD_SHARE = 0.25


def _word_lang(word: str) -> str | None:
    c = count_scripts(word)
    best = max(c, key=c.get)
    return best if c[best] else None


def dominant_language(text: str) -> tuple[str | None, float]:
    """Return (matrix language, confidence) for a transcript or reply, or (None, 0.0).

    Word level: each whitespace token is assigned the script of most of its letters.
    Code-mixed Indic/Japanese speech borrows English words, not the other way round, so
    if native-script words are at least NATIVE_MIN_WORD_SHARE of all words, the most
    frequent native script wins ("मेरे credit card का payment कब है?" -> hi). Otherwise
    the text is English (romanized Hindi/Bengali also lands here: LID must decide those).

    Confidence for a native script = its share of the native-script words (1.0 when only
    one non-Latin script occurs); for English = share of Latin words. Accuracy of this
    heuristic on the mixed test lines is measured in M0 (run_lid.py, run_llm.py).
    """
    langs = [l for l in (_word_lang(w) for w in unicodedata.normalize("NFC", text).split()) if l]
    if not langs:
        return None, 0.0
    counts = {l: langs.count(l) for l in LANGS}
    native = {l: n for l, n in counts.items() if l != "en" and n}
    if native:
        top = max(native, key=native.get)
        if native[top] / len(langs) >= NATIVE_MIN_WORD_SHARE:
            return top, native[top] / sum(native.values())
    return "en", counts["en"] / len(langs)


def is_native_script(text: str, lang: str, min_share: float = 0.6) -> bool:
    """True if `text` is mostly written in the native script of `lang`.

    English loanwords in Latin are tolerated up to (1 - min_share) of letters.
    """
    counts = count_scripts(text)
    total = sum(counts.values())
    if total == 0:
        return False
    return counts.get(lang, 0) / total >= min_share


def find_digits(text: str) -> list[str]:
    """Digits of any supported script found in `text` (replies must have none)."""
    out = []
    for ch in text:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _DIGIT_RANGES):
            out.append(ch)
    return out
