"""Scrub API keys from logs, tracebacks and stored transcripts (CLAUDE.md)."""
from __future__ import annotations

import logging
import re

_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")
_TOKEN = re.compile(r"(token=)[A-Za-z0-9_\-.%]+")  # signed session tokens in WebSocket URLs
_extra: set[str] = set()


def register_secret(value: str | None) -> None:
    if value and len(value) >= 8:
        _extra.add(value)


def scrub(text: str) -> str:
    if not text:
        return text
    text = _PATTERN.sub("sk-ant-***REDACTED***", text)
    text = _TOKEN.sub(r"\1***", text)
    for s in _extra:
        text = text.replace(s, "***REDACTED***")
    return text


class _Filter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(scrub(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: scrub(v) if isinstance(v, str) else v for k, v in record.args.items()}
        if record.exc_info and record.exc_info[1] is not None:
            import traceback

            text = scrub("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
            record.exc_text = text
        return True


def install() -> None:
    """Attach the scrubber to stdlib logging (incl. uvicorn) and loguru (Pipecat)."""
    f = _Filter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "httpx", "anthropic"):
        lg = logging.getLogger(name)
        lg.addFilter(f)
        for h in lg.handlers:
            h.addFilter(f)
    try:
        from loguru import logger

        logger.configure(patcher=lambda r: r.update(message=scrub(r["message"])))
    except Exception:
        pass
