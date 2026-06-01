"""
Room Reader — Emotional State Detection from Conversational Signals

Detects user emotional state from text using multi-signal analysis:
- Keyword patterns (frustration, confusion, excitement, etc.)
- Syntactic markers (sentence structure, punctuation intensity)
- Discourse markers (hedging, self-correction, escalation)
- Emotional trajectory (sliding window of recent interactions)

Returns confidence-scored state readings that hooks.py uses
for adaptive personality injection.

Lightweight: ~200 lines, zero external dependencies, no ML inference.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .storage import atomic_write_json, read_json_object


# ---------------------------------------------------------------------------
# Signal patterns — multi-layered detection
# ---------------------------------------------------------------------------

# Layer 1: Keyword signals (direct emotional indicators)
_KEYWORD_SIGNALS: dict[str, list[str]] = {
    "frustrated": [
        "not working", "broken", "still failing", "keeps failing",
        "doesn't work", "can't figure", "tried everything",
        "this is wrong", "error again", "what the hell",
        "nothing works", "so frustrated", "driving me crazy",
        "why won't", "still broken", "same error", "waste of time",
    ],
    "confused": [
        "don't understand", "makes no sense", "what does this mean",
        "i'm lost", "confused", "unclear", "what's going on",
        "how does this", "why is this", "i thought",
        "wait what", "that doesn't", "but i expected",
    ],
    "excited": [
        "this is amazing", "it works", "finally", "awesome",
        "perfect", "brilliant", "exactly what", "love this",
        "incredible", "so cool", "yes!", "nailed it",
    ],
    "vulnerable": [
        "sorry", "my fault", "i'm bad at", "dumb question",
        "probably obvious", "i should know", "forgive me",
        "don't judge", "embarrassing", "i feel stupid",
    ],
    "defensive": [
        "i already tried", "i know what", "that's not the issue",
        "you're wrong", "that won't work", "i said",
        "listen", "no that's", "obviously",
    ],
    "exhausted": [
        "been at this for", "hours", "all day", "give up",
        "tired", "burnt out", "can't anymore", "done with",
        "just want it to work", "over it", "exhausted",
    ],
    "curious": [
        "how does", "why does", "what if", "interesting",
        "tell me more", "curious about", "i wonder",
        "is it possible", "could we", "what about",
    ],
    "expert": [
        "i know", "obviously", "clearly", "just need",
        "simple fix", "skip the explanation", "i've done this",
        "in my experience", "the issue is", "root cause",
    ],
    "rushed": [
        "asap", "urgent", "deadline", "hurry", "quickly",
        "right now", "immediately", "time sensitive", "ship it",
        "just make it work", "no time", "crunch",
    ],
}

# Layer 2: Syntactic signals (structural patterns)
_SYNTACTIC_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "frustrated": [
        (r"[!?]{2,}", 0.6),          # Multiple !! or ??
        (r"\b(still|again|yet)\b", 0.3),  # Repetition indicators
        (r"^(why|how come)\b", 0.3),  # Why-questions (blame frame)
    ],
    "confused": [
        (r"\?{2,}", 0.5),            # Multiple question marks
        (r"\b(but|however|though)\b.*\?", 0.4),  # Contradictory questions
        (r"\.\.\.", 0.3),            # Trailing off (uncertainty)
    ],
    "excited": [
        (r"[!]{2,}", 0.5),           # Multiple exclamation marks
        (r"\b[A-Z]{3,}\b", 0.4),     # ALL CAPS words
    ],
    "rushed": [
        (r"\b(just|quick|fast)\b", 0.3),  # Speed indicators
        (r"^(do|fix|make|run)\b", 0.3),   # Imperative starts
    ],
    "exhausted": [
        (r"\b(sigh|ugh|meh)\b", 0.5),  # Fatigue markers
    ],
}

# Layer 3: Discourse markers (conversational repair / escalation)
_DISCOURSE_MARKERS: dict[str, list[tuple[str, float]]] = {
    "frustrated": [
        ("i already told you", 0.7),
        ("as i said", 0.5),
        ("like i mentioned", 0.5),
        ("for the nth time", 0.8),
    ],
    "confused": [
        ("i thought you said", 0.6),
        ("but earlier", 0.5),
        ("wait, so", 0.4),
        ("let me get this straight", 0.5),
    ],
    "vulnerable": [
        ("sorry to bother", 0.6),
        ("this might be stupid", 0.7),
        ("i know this is basic", 0.5),
    ],
    "defensive": [
        ("that's not what i meant", 0.6),
        ("you're not listening", 0.7),
        ("i never said", 0.5),
    ],
}


# ---------------------------------------------------------------------------
# State reading result
# ---------------------------------------------------------------------------

@dataclass
class RoomReading:
    """Result of reading the room — what emotional state(s) we detect."""
    primary_state: Optional[str] = None
    confidence: float = 0.0
    all_states: dict[str, float] = field(default_factory=dict)
    signals_found: int = 0
    trajectory: str = "stable"  # rising | falling | stable | volatile


# ---------------------------------------------------------------------------
# Trajectory tracker — sliding window across interactions
# ---------------------------------------------------------------------------

_TRAJECTORY_FILE = Path.home() / ".cache" / "personality-chips" / "room_trajectory.json"
_WINDOW_SIZE = 8  # Track last N interactions
_TRAJECTORY_TTL = 1800  # 30 minutes — reset if gap exceeds this


def _load_trajectory() -> list[dict]:
    """Load the sliding window of recent readings."""
    data = read_json_object(_TRAJECTORY_FILE)
    if data is None:
        return []
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        return []
    now = time.time()
    return [
        entry for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("ts", 0), (int, float))
        and now - entry.get("ts", 0) < _TRAJECTORY_TTL
    ]


def _save_trajectory(entries: list[dict]) -> None:
    """Persist the sliding window."""
    trimmed = entries[-_WINDOW_SIZE:]
    atomic_write_json(_TRAJECTORY_FILE, {"entries": trimmed}, raise_on_error=False)


def _compute_trajectory(entries: list[dict], current_score: float) -> str:
    """Compute emotional trajectory from sliding window.

    Returns: rising | falling | stable | volatile
    """
    if len(entries) < 2:
        return "stable"

    scores = [e.get("score", 0.0) for e in entries[-4:]] + [current_score]
    if len(scores) < 3:
        return "stable"

    deltas = [scores[i] - scores[i - 1] for i in range(1, len(scores))]

    # Check for volatility (big swings)
    if any(abs(d) > 0.3 for d in deltas):
        return "volatile"

    avg_delta = sum(deltas) / len(deltas)
    if avg_delta > 0.1:
        return "rising"
    elif avg_delta < -0.1:
        return "falling"
    return "stable"


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def read_room(text: str, persist_trajectory: bool = True) -> RoomReading:
    """Read the emotional room from text input.

    Analyzes text across three signal layers (keywords, syntax, discourse),
    tracks trajectory across interactions, and returns a confidence-scored
    reading of the user's emotional state.

    Args:
        text: The text to analyze (user message, tool description, etc.)
        persist_trajectory: Whether to update the sliding window on disk

    Returns:
        RoomReading with primary state, confidence, and trajectory
    """
    if not text or not text.strip():
        return RoomReading()

    text_lower = text.lower()
    state_scores: dict[str, float] = {}
    total_signals = 0

    # Layer 1: Keywords
    for state, keywords in _KEYWORD_SIGNALS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits:
            score = min(hits * 0.25, 0.8)
            state_scores[state] = state_scores.get(state, 0.0) + score
            total_signals += hits

    # Layer 2: Syntactic patterns (no IGNORECASE — case matters for structural signals)
    for state, patterns in _SYNTACTIC_PATTERNS.items():
        for pattern, weight in patterns:
            if re.search(pattern, text):
                state_scores[state] = state_scores.get(state, 0.0) + weight
                total_signals += 1

    # Layer 3: Discourse markers
    for state, markers in _DISCOURSE_MARKERS.items():
        for marker, weight in markers:
            if marker in text_lower:
                state_scores[state] = state_scores.get(state, 0.0) + weight
                total_signals += 1

    if not state_scores:
        return RoomReading()

    # Normalize scores to 0-1
    max_score = max(state_scores.values())
    if max_score > 1.0:
        state_scores = {k: min(v / max_score, 1.0) for k, v in state_scores.items()}

    # Find primary state
    primary = max(state_scores, key=state_scores.get)
    confidence = state_scores[primary]

    # Only report if confidence exceeds threshold
    if confidence < 0.2:
        return RoomReading()

    # Trajectory tracking
    trajectory_entries = _load_trajectory() if persist_trajectory else []
    trajectory = _compute_trajectory(trajectory_entries, confidence)

    if persist_trajectory:
        trajectory_entries.append({
            "ts": time.time(),
            "state": primary,
            "score": round(confidence, 3),
        })
        _save_trajectory(trajectory_entries)

    return RoomReading(
        primary_state=primary,
        confidence=round(confidence, 3),
        all_states={k: round(v, 3) for k, v in state_scores.items() if v >= 0.15},
        signals_found=total_signals,
        trajectory=trajectory,
    )


def read_room_from_hook_input(tool_input: dict) -> RoomReading:
    """Read the room from Claude Code hook tool_input dict.

    Extracts text from command, description, old_string, new_string,
    content, and file_path fields.
    """
    text_parts = []
    for key in ("command", "description", "old_string", "new_string", "content"):
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            text_parts.append(val)

    # File paths can hint at urgency (hotfix, quick-fix, etc.)
    fp = tool_input.get("file_path", "")
    if isinstance(fp, str) and fp:
        text_parts.append(fp)

    return read_room(" ".join(text_parts)) if text_parts else RoomReading()


def get_trajectory_summary() -> dict:
    """Get a summary of recent emotional trajectory for context injection."""
    entries = _load_trajectory()
    if not entries:
        return {"trajectory": "stable", "recent_states": [], "interaction_count": 0}

    recent = entries[-_WINDOW_SIZE:]
    states = [e.get("state", "neutral") for e in recent]
    scores = [e.get("score", 0.0) for e in recent]

    return {
        "trajectory": _compute_trajectory(recent, scores[-1] if scores else 0.0),
        "recent_states": states,
        "interaction_count": len(recent),
        "avg_intensity": round(sum(scores) / len(scores), 3) if scores else 0.0,
    }
