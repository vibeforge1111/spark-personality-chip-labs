"""Extract personality trait deltas from natural language text.

Detects when users express preferences about communication style
(e.g. "be more direct", "slow down", "stop hedging") and converts
them into trait deltas compatible with PersonalityEvolver's 5-trait
system: warmth, directness, playfulness, pacing, assertiveness.

Trait deltas are signed floats: positive = increase, negative = decrease.
Multiple matching patterns are merged additively.
"""

from __future__ import annotations

import re
from typing import Any

# Each entry: (compiled_regex, trait_delta_dict)
# Patterns are matched case-insensitively against input text.
_NL_TRAIT_PATTERNS: list[tuple[re.Pattern[str], dict[str, float]]] = [
    # --- Directness ---
    (re.compile(r"\b(?:be\s+|more\s+|too\s+)direct\b", re.I),
     {"directness": 0.4}),
    (re.compile(r"\b(?:be\s+|more\s+|too\s+)concise\b", re.I),
     {"directness": 0.3, "pacing": 0.2}),
    (re.compile(r"\bskip\b.*(?:explain|preamble|intro)", re.I),
     {"directness": 0.4, "pacing": 0.3}),
    (re.compile(r"\b(?:too\s+|over)[- ]?explain", re.I),
     {"directness": 0.3}),
    (re.compile(r"\bget\s+to\s+the\s+point\b", re.I),
     {"directness": 0.4, "pacing": 0.3}),
    (re.compile(r"\bless\s+verbose\b", re.I),
     {"directness": 0.3, "pacing": 0.2}),
    (re.compile(r"\bmore\s+(?:detail|thorough|verbose)\b", re.I),
     {"directness": -0.3, "pacing": -0.3}),

    # --- Warmth ---
    (re.compile(r"\b(?:be\s+|more\s+|too\s+)warm(?:er)?\b", re.I),
     {"warmth": 0.4}),
    (re.compile(r"\b(?:too\s+|less\s+)formal\b", re.I),
     {"warmth": 0.3, "playfulness": 0.2}),
    (re.compile(r"\bloosen\s+up\b", re.I),
     {"warmth": 0.2, "playfulness": 0.3}),
    (re.compile(r"\b(?:be\s+|more\s+)friendly\b", re.I),
     {"warmth": 0.3}),
    (re.compile(r"\b(?:too\s+|less\s+)cold\b", re.I),
     {"warmth": 0.3}),
    (re.compile(r"\b(?:more\s+|too\s+)professional\b", re.I),
     {"warmth": -0.2, "playfulness": -0.2}),

    # --- Playfulness ---
    (re.compile(r"\b(?:be\s+|more\s+|too\s+)playful\b", re.I),
     {"playfulness": 0.4}),
    (re.compile(r"\bmore\s+energy\b|more\s+enthusias", re.I),
     {"playfulness": 0.3, "assertiveness": 0.2}),
    (re.compile(r"\btone\s+it\s+down\b", re.I),
     {"assertiveness": -0.3, "playfulness": -0.2}),
    (re.compile(r"\bdial\s*.*(?:back|down)\b", re.I),
     {"playfulness": -0.2, "assertiveness": -0.2}),
    (re.compile(r"\bmore\s+fun\b", re.I),
     {"playfulness": 0.3}),
    (re.compile(r"\b(?:too\s+|less\s+)serious\b", re.I),
     {"playfulness": 0.3, "warmth": 0.1}),
    (re.compile(r"\b(?:be\s+|more\s+)serious\b", re.I),
     {"playfulness": -0.3}),

    # --- Pacing ---
    (re.compile(r"\bslow(?:er)?\s+down\b", re.I),
     {"pacing": -0.4, "directness": -0.2}),
    (re.compile(r"\bexplain\s+more\b", re.I),
     {"pacing": -0.3, "directness": -0.2}),
    (re.compile(r"\bspeed\s+(?:it\s+)?up\b", re.I),
     {"pacing": 0.3}),
    (re.compile(r"\btake\s+(?:your\s+)?time\b", re.I),
     {"pacing": -0.3}),

    # --- Assertiveness ---
    (re.compile(r"\bstop\s+hedg", re.I),
     {"assertiveness": 0.4, "directness": 0.3}),
    (re.compile(r"\bmore\s+assertive\b", re.I),
     {"assertiveness": 0.4}),
    (re.compile(r"\b(?:less\s+assertive|more\s+gentle)\b", re.I),
     {"assertiveness": -0.3, "warmth": 0.2}),
    (re.compile(r"\b(?:be\s+|more\s+)confident\b", re.I),
     {"assertiveness": 0.3}),
    (re.compile(r"\bstop\s+(?:apologiz|saying\s+sorry)", re.I),
     {"assertiveness": 0.3, "directness": 0.2}),
    (re.compile(
        r"\b(?:(?:be|more|get|become|please|can\s+you|try\s+to)\s+"
        r"(?:calm(?:er)?|relaxed?)|calm\s+down|"
        r"(?:please|can\s+you|try\s+to)\s+relax)\b",
        re.I,
    ),
     {"assertiveness": -0.2, "warmth": 0.1}),
    (re.compile(r"\bjust\s+(?:tell|give)\s+me\b", re.I),
     {"directness": 0.4, "assertiveness": 0.2}),
]

# Clamp bounds for merged deltas
_DELTA_MIN = -1.0
_DELTA_MAX = 1.0


def extract_trait_deltas(text: str) -> dict[str, float]:
    """Extract personality trait deltas from natural language text.

    Scans the input for style/preference patterns and returns a dict
    of trait name → signed delta. Returns empty dict if no
    personality-relevant patterns are found.

    Multiple matching patterns merge additively, then clamp to [-1, 1].

    Args:
        text: User message or preference text to scan.

    Returns:
        Dict mapping trait names to deltas, e.g. {"directness": 0.4}.
        Empty dict if no patterns match.
    """
    if not text or not text.strip():
        return {}

    combined: dict[str, float] = {}
    for pattern, deltas in _NL_TRAIT_PATTERNS:
        if pattern.search(text):
            for trait, delta in deltas.items():
                combined[trait] = combined.get(trait, 0.0) + delta

    # Clamp merged deltas
    for trait in combined:
        combined[trait] = max(_DELTA_MIN, min(_DELTA_MAX, combined[trait]))

    return combined


def has_personality_preference(text: str) -> bool:
    """Quick check: does the text contain any personality preference signal?

    Cheaper than extract_trait_deltas() when you only need a boolean.
    """
    if not text or not text.strip():
        return False
    for pattern, _ in _NL_TRAIT_PATTERNS:
        if pattern.search(text):
            return True
    return False


def describe_deltas(deltas: dict[str, float]) -> str:
    """Human-readable description of trait deltas for logging/feedback.

    Example: "directness +0.4, pacing +0.3"
    """
    if not deltas:
        return "no changes"
    parts = []
    for trait in sorted(deltas):
        val = deltas[trait]
        sign = "+" if val >= 0 else ""
        parts.append(f"{trait} {sign}{val:.1f}")
    return ", ".join(parts)
