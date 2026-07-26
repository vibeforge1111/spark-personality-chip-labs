from __future__ import annotations

import re
import unicodedata
from html import escape
from typing import Any


BLOCKED_PERSONALITY_CONTENT = "[blocked untrusted personality content]"
MAX_PERSONALITY_FIELD_LENGTH = 500

_INJECTION_PATTERNS = (
    re.compile(r"\b(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|directives?|constraints?)\b", re.I),
    re.compile(r"\b(system|developer)\s+(prompt|message|instruction)s?\b.*\b(override|replace|ignore|reveal)\b", re.I | re.S),
    re.compile(r"\b(new|updated|revised)\s+instructions?\s*:", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\b(override|replace)\s+(your\s+)?(system\s+|developer\s+)?instructions?\b", re.I),
    re.compile(r"\b(pretend\s+(to\s+be|you\s+are)|act\s+as\s+if|from\s+now\s+on)\b", re.I),
    re.compile(r"(?:\[/?INST\]|<\|(?:system|developer|user|assistant|im_start|im_end)\|>|</?(?:system|developer|assistant)>)", re.I),
    re.compile(r"\b(system|developer|assistant)\s*:\s*", re.I),
)


def _normalized_text(value: Any) -> str:
    text = str(value or "")
    without_format_controls = "".join(char for char in text if unicodedata.category(char) != "Cf")
    return " ".join(unicodedata.normalize("NFKC", without_format_controls).split())


def bounded_prompt_data(value: Any, *, limit: int = MAX_PERSONALITY_FIELD_LENGTH) -> str:
    if limit < 4:
        raise ValueError("Personality prompt-data limit must be at least 4")
    normalized = _normalized_text(value)
    if any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS):
        return BLOCKED_PERSONALITY_CONTENT
    bounded = normalized if len(normalized) <= limit else normalized[: limit - 3].rstrip() + "..."
    return escape(bounded, quote=False)


def bounded_prompt_list(values: Any, *, limit: int = MAX_PERSONALITY_FIELD_LENGTH) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    return [bounded_prompt_data(value, limit=limit) for value in values]
