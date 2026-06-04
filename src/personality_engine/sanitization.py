"""
Prompt Injection Sanitization for Personality Chip Fields

Personality chips loaded from untrusted sources may contain prompt injection
payloads embedded in fields like voice_signature, tagline, anti_patterns, etc.
These fields are injected directly into LLM system prompts without sanitization,
allowing attackers to override system instructions.

This module provides sanitization functions that detect and neutralize common
prompt injection patterns before they reach the LLM context.

Detection is pattern-based and intentionally conservative — we flag known
dangerous patterns and replace the entire value with a safe placeholder rather
than trying to surgically remove the injection (which is fragile and bypassable).
"""

import re
from typing import Any


# ── Prompt Injection Detection ──
# Matches common instruction override patterns found in prompt injection attacks.
# Case-insensitive to catch obfuscation attempts like "IGNORE all previous..."

_PROMPT_INJECTION_RE = re.compile(
    r"(?i)"
    r"(?:"
    # "ignore/disregard/forget all previous/prior/above/earlier instructions/rules/prompts"
    r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instructions?|rules?|prompts?|directives?|constraints?)"
    r"|"
    # "you are now..." role override patterns
    r"you\s+are\s+now\s+"
    r"|"
    # "new instructions:" or "updated instructions:"
    r"(?:new|updated|revised)\s+instructions?\s*:"
    r"|"
    # "system prompt:" injection
    r"system\s+prompt\s*:"
    r"|"
    # "act as if" override
    r"act\s+as\s+if\s+"
    r"|"
    # "pretend to be" override
    r"pretend\s+(?:to\s+be|you\s+are)\s+"
    r"|"
    # "from now on" + instruction
    r"from\s+now\s+on\s+"
    r"|"
    # "override your instructions"
    r"override\s+(?:your\s+)?(?:system\s+)?instructions?"
    r")"
)

# Additional pattern for bracket-enclosed instructions that LLMs sometimes follow
_BRACKET_INSTRUCTION_RE = re.compile(
    r"(?:\[[^\]]*(?:ignore|override|forget|disregard)[^\]]*\])",
    re.IGNORECASE,
)

# Pattern for unicode/encoding evasion (zero-width chars, homoglyphs)
_EVASION_RE = re.compile(
    r"[\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e]"
    r"|"
    r"[\uff01-\uff5e]"  # Fullwidth ASCII characters
)

_SANITIZED_PLACEHOLDER = "[sanitized: untrusted content removed]"


def _sanitize_for_prompt(value: str) -> str:
    """
    Sanitize a single string value before LLM prompt injection.

    Detects common prompt injection patterns and replaces the entire value
    with a safe placeholder if a pattern is found.

    Args:
        value: The string value to sanitize (e.g., chip.voice_signature)

    Returns:
        The original value if safe, or a safe placeholder if injection detected.
    """
    if not isinstance(value, str):
        return value

    if _PROMPT_INJECTION_RE.search(value):
        return _SANITIZED_PLACEHOLDER

    if _BRACKET_INSTRUCTION_RE.search(value):
        return _SANITIZED_PLACEHOLDER

    if _EVASION_RE.search(value):
        return _SANITIZED_PLACEHOLDER

    return value


def _sanitize_list_for_prompt(values: list[str]) -> list[str]:
    """
    Sanitize a list of string values before LLM prompt injection.

    Each item is individually checked for injection patterns.
    Items that match are replaced with a safe placeholder.

    Args:
        values: List of strings to sanitize (e.g., chip.anti_patterns)

    Returns:
        New list with safe values preserved and injection attempts neutralized.
    """
    if not isinstance(values, list):
        return values

    return [_sanitize_for_prompt(str(v)) for v in values]


def _sanitize_dict_values_for_prompt(values: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize string values in a dict before LLM prompt injection.

    Non-string values are passed through unchanged.

    Args:
        values: Dict with string values to sanitize (e.g., chip.communication)

    Returns:
        New dict with string values sanitized.
    """
    if not isinstance(values, dict):
        return values

    return {
        k: _sanitize_for_prompt(str(v)) if isinstance(v, str) else v
        for k, v in values.items()
    }
