"""Per-turn language decision (PLAN.md section 6, CLAUDE.md language routing rules).

Thresholds are NOT guessed here: defaults are placeholders until M0 writes
measured values to eval/results.md and agent/engines.json.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent.lang.script import LANGS, dominant_language


@dataclass
class LangDecision:
    language: str
    reason: str  # override | lid | script_flip | low_conf_keep_prev | default


def restrict_probs(all_probs: dict[str, float], candidates=LANGS) -> dict[str, float]:
    """Renormalize a LID distribution over the enabled candidate languages."""
    sub = {k: all_probs.get(k, 0.0) for k in candidates}
    s = sum(sub.values())
    if s <= 0:
        return {k: 0.0 for k in candidates}
    return {k: v / s for k, v in sub.items()}


def bias_previous(probs: dict[str, float], prev: str | None, bias: float) -> dict[str, float]:
    """Add `bias` to the previous language's probability and renormalize."""
    if not prev or prev not in probs or bias <= 0:
        return probs
    p = dict(probs)
    p[prev] += bias
    s = sum(p.values())
    return {k: v / s for k, v in p.items()}


def decide_language(
    lid_probs: dict[str, float] | None,
    transcript: str | None,
    prev_lang: str | None,
    default_lang: str = "en",
    threshold: float = 0.5,
    prev_bias: float = 0.1,
    override: str | None = None,
    script_min_share: float = 0.6,
) -> LangDecision:
    """Decide the turn language.

    Order: manual override > script of transcript (if clearly non-Latin and
    disagreeing) > LID above threshold > keep previous language > default.
    """
    if override:
        return LangDecision(override, "override")

    lid_lang, lid_conf = None, 0.0
    if lid_probs:
        p = bias_previous(restrict_probs(lid_probs), prev_lang, prev_bias)
        lid_lang = max(p, key=p.get)
        lid_conf = p[lid_lang]

    if transcript:
        s_lang, share = dominant_language(transcript)
        # A clearly native non-Latin script is strong evidence; Latin is not
        # (romanized Hindi/Bengali looks like English), so it never flips.
        if s_lang and s_lang != "en" and share >= script_min_share and s_lang != lid_lang:
            return LangDecision(s_lang, "script_flip")

    if lid_lang and lid_conf >= threshold:
        return LangDecision(lid_lang, "lid")
    if prev_lang:
        return LangDecision(prev_lang, "low_conf_keep_prev")
    return LangDecision(lid_lang or default_lang, "default")
