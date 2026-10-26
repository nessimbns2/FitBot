"""
app/core/privacy.py
Privacy and output guardrails around every LLM call.

* `redact_pii` — raw personal data is never forwarded to the LLM: emails, phone numbers,
  card / IBAN-like numbers, URLs with credentials and the user's own name are masked.
* `validate_llm_output` — the model's answer is checked before it is displayed:
  trimmed, length-capped, stripped of HTML/script tags and of leaked system-prompt markers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Phone numbers: international (+216 …, 0033 …), 8–15 contiguous digits, Tunisian 2-3-3
# and French 2-2-2-2-2 groupings. Deliberately narrow so workout numbers ("100 100 95") survive.
_PHONE_RE = re.compile(
    r"(?<![\w.])(?:"
    r"(?:\+|00)\d[\d\s.\-()]{6,18}\d"
    r"|\d{8,15}"
    r"|\d{2}[\s.\-]\d{3}[\s.\-]\d{3}"
    r"|0\d(?:[\s.\-]\d{2}){4}"
    r")(?![\w.])"
)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_CREDENTIAL_URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@\S+", re.IGNORECASE)

_TAG_RE = re.compile(r"<\s*/?\s*(script|style|iframe|object|embed)[^>]*>", re.IGNORECASE)
_LEAK_MARKERS = ("SYSTEM:", "USER:", "ASSISTANT:")

MAX_OUTPUT_CHARS = 8000


def redact_pii(text: str, known_names: Iterable[str] | None = None) -> str:
    """Mask personal identifiers in free text before it is sent to an external LLM."""
    if not text:
        return text
    redacted = _CREDENTIAL_URL_RE.sub("[url]", text)
    redacted = _EMAIL_RE.sub("[email]", redacted)
    redacted = _IBAN_RE.sub("[iban]", redacted)
    redacted = _CARD_RE.sub(lambda m: "[number]" if len(re.sub(r"\D", "", m.group())) >= 13 else m.group(), redacted)
    redacted = _PHONE_RE.sub("[phone]", redacted)

    for name in known_names or ():
        for part in {name.strip(), *name.split()}:
            # Only mask name tokens long enough not to clash with ordinary words.
            if len(part) >= 3:
                redacted = re.sub(rf"\b{re.escape(part)}\b", "[name]", redacted, flags=re.IGNORECASE)
    return redacted


def validate_llm_output(text: str | None, fallback: str = "") -> str:
    """Return a display-safe version of an LLM answer (or `fallback` if nothing usable)."""
    if not text or not text.strip():
        return fallback
    cleaned = _TAG_RE.sub("", text).strip()

    # If the model echoed our prompt scaffolding, keep only what precedes the leak.
    for marker in _LEAK_MARKERS:
        idx = cleaned.find(f"\n{marker}")
        if idx > 0:
            cleaned = cleaned[:idx].rstrip()
    if cleaned.startswith("ASSISTANT:"):
        cleaned = cleaned[len("ASSISTANT:"):].lstrip()

    if len(cleaned) > MAX_OUTPUT_CHARS:
        cleaned = cleaned[:MAX_OUTPUT_CHARS].rstrip() + "…"
    return cleaned or fallback
