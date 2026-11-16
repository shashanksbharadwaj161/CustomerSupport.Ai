"""Site brief: Claude reads the cleaned pages once per crawl and writes structured facts (cached in the prompt)."""
from __future__ import annotations

BRIEF_SYSTEM = """You write a factual site brief for a customer-support voice agent.
Use ONLY facts stated in the pages. Do not invent anything. If a section has no facts, write "not stated".
Plain text, no markdown tables. Sections, in this order:
Business summary / Products and services / Prices / Hours / Contacts / Policies / FAQs.
Keep it under 600 words."""

MAX_INPUT_CHARS = 60000


def brief_prompt(pages) -> str:
    parts, n = [], 0
    for p in pages:
        block = f"=== {p.title} ({p.url})\n{p.text}\n"
        if n + len(block) > MAX_INPUT_CHARS:
            parts.append(f"[... {len(pages) - len(parts)} more pages truncated for length ...]")
            break
        parts.append(block)
        n += len(block)
    return "Website pages:\n\n" + "\n".join(parts)
