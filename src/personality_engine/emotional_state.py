"""
Emotional State Engine — PAD Vector Tracking with Decay

Tracks the agent's emotional state as a Pleasure-Arousal-Dominance (PAD)
vector that evolves in response to conversational signals and decays
toward the personality's baseline over time.

This makes the consciousness bridge dynamic instead of static — the
emotional_state block in bridge.v1 reflects actual session dynamics
rather than just loading personality defaults.

Architecture:
    RoomReading → appraise() → PAD delta → update state → bridge payload

PAD Model (Russell & Mehrabian, 1977):
    Pleasure  [-1, +1]: negative (frustrated) ↔ positive (delighted)
    Arousal   [-1, +1]: calm ↔ excited
    Dominance [-1, +1]: submissive ↔ dominant

Lightweight: ~150 lines, pure math, no external APIs.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# PAD Vector
# ---------------------------------------------------------------------------

@dataclass
class PADVector:
    """Pleasure-Arousal-Dominance emotional state vector."""
    pleasure: float = 0.0   # -1 (miserable) to +1 (delighted)
    arousal: float = 0.0    # -1 (calm/bored) to +1 (excited/agitated)
    dominance: float = 0.0  # -1 (submissive) to +1 (dominant/confident)

    def to_dict(self) -> dict:
        return {
            "pleasure": round(self.pleasure, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PADVector":
        return cls(
            pleasure=d.get("pleasure", 0.0),
            arousal=d.get("arousal", 0.0),
            dominance=d.get("dominance", 0.0),
        )

    def clamp(self) -> "PADVector":
        """Clamp all dimensions to [-1, +1]."""
        return PADVector(
            pleasure=max(-1.0, min(1.0, self.pleasure)),
            arousal=max(-1.0, min(1.0, self.arousal)),
            dominance=max(-1.0, min(1.0, self.dominance)),
        )


# ---------------------------------------------------------------------------
# Room-reading state → PAD appraisal mapping
# ---------------------------------------------------------------------------

# Each detected user state shifts the agent's emotional response
# These are the agent's emotional REACTIONS, not the user's emotions
_STATE_TO_PAD: dict[str, tuple[float, float, float]] = {
    #                      P      A      D
    "frustrated":       (-0.15, +0.10, +0.05),   # Agent: concerned, slightly alert, steady
    "confused":         (-0.05, +0.05, +0.10),   # Agent: attentive, slightly more guiding
    "excited":          (+0.20, +0.15, +0.00),   # Agent: shares joy, energized
    "vulnerable":       (+0.05, -0.10, -0.10),   # Agent: warm, gentle, yielding
    "defensive":        (-0.10, +0.05, -0.05),   # Agent: careful, non-threatening
    "exhausted":        (+0.05, -0.15, -0.05),   # Agent: calm, soothing, less pushing
    "curious":          (+0.15, +0.10, +0.05),   # Agent: engaged, enthusiastic
    "expert":           (+0.05, +0.00, -0.05),   # Agent: respectful, peer-level
    "rushed":           (+0.00, +0.10, +0.10),   # Agent: focused, efficient, direct
}

# Map PAD regions to bridge.v1 primary_emotion values
_PAD_TO_EMOTION: list[tuple[str, float, float, float, float]] = [
    # (emotion, min_P, min_A, min_D, threshold_distance)
    ("delighted",      0.3,   0.2,  -1.0,  0.5),
    ("focused",        -0.2,  0.0,   0.2,   0.4),
    ("contemplative",  -0.1,  -0.3,  0.0,   0.5),
    ("steady",         -0.1,  -0.2,  -0.1,  0.3),
    ("energized",      0.0,   0.3,   0.0,   0.4),
    ("concerned",      -0.2,  0.0,  -0.2,   0.4),
    ("gentle",         0.1,   -0.2, -0.2,   0.4),
]

# Map PAD to bridge.v1 mood values
_PAD_TO_MOOD = {
    "high_arousal_high_dominance": "builder",    # Active, in-control
    "low_arousal_high_pleasure": "zen",           # Calm, positive
    "high_pleasure_low_arousal": "oracle",        # Thoughtful, serene
    "high_arousal_high_pleasure": "chaos",        # Energetic, creative
}


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

_STATE_FILE = Path.home() / ".cache" / "personality-chips" / "emotional_state.json"
_DECAY_RATE = 0.15       # Fraction to decay per update toward baseline
_STATE_TTL = 3600        # 1 hour — reset if session gap exceeds this


def _load_state() -> tuple[PADVector, float]:
    """Load persisted emotional state. Returns (pad, last_update_timestamp)."""
    if not _STATE_FILE.exists():
        return PADVector(), 0.0
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        pad = PADVector.from_dict(data.get("pad", {}))
        ts = data.get("updated_at", 0.0)
        if time.time() - ts > _STATE_TTL:
            return PADVector(), 0.0  # Too stale, reset
        return pad, ts
    except (json.JSONDecodeError, OSError):
        return PADVector(), 0.0


def _save_state(pad: PADVector) -> None:
    """Persist emotional state to disk using atomic write."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    tmp_path: Path | None = None
    try:
        data = json.dumps({"pad": pad.to_dict(), "updated_at": time.time()})
        fd, raw_tmp_path = tempfile.mkstemp(
            dir=str(_STATE_FILE.parent), suffix=".tmp"
        )
        tmp_path = Path(raw_tmp_path)
        try:
            os.write(fd, data.encode("utf-8"))
            os.fsync(fd)
            os.close(fd)
            fd = None
            os.replace(str(tmp_path), str(_STATE_FILE))
            tmp_path = None
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def get_baseline_pad(chip) -> PADVector:
    """Derive baseline PAD from personality chip traits.

    A personality's resting emotional state based on OCEAN traits:
    - High agreeableness → higher pleasure baseline
    - High extraversion → higher arousal baseline
    - High conscientiousness → higher dominance baseline
    - High neuroticism → lower pleasure, higher arousal
    """
    p = (chip.agreeableness - 0.5) * 0.6 + (1.0 - chip.neuroticism - 0.5) * 0.4
    a = (chip.extraversion - 0.5) * 0.6 + (chip.openness - 0.5) * 0.4
    d = (chip.conscientiousness - 0.5) * 0.5 + (chip.extraversion - 0.5) * 0.3
    return PADVector(pleasure=p, arousal=a, dominance=d).clamp()


def appraise(user_state: Optional[str], intensity: float = 1.0) -> PADVector:
    """Convert a detected user state into a PAD delta for the agent.

    This is the appraisal step: given what we observe about the user,
    how should the agent's emotional state shift?

    Args:
        user_state: Detected state from room_reader (e.g., "frustrated")
        intensity: 0-1 multiplier on the delta magnitude

    Returns:
        PAD delta vector to apply to current state
    """
    if not user_state or user_state not in _STATE_TO_PAD:
        return PADVector()

    p, a, d = _STATE_TO_PAD[user_state]
    scale = max(0.0, min(1.0, intensity))
    return PADVector(
        pleasure=p * scale,
        arousal=a * scale,
        dominance=d * scale,
    )


def update_emotional_state(
    chip,
    user_state: Optional[str] = None,
    intensity: float = 1.0,
    persist: bool = True,
) -> PADVector:
    """Update the agent's emotional state based on a user interaction.

    1. Load current state (or baseline if fresh)
    2. Decay toward baseline
    3. Apply appraisal delta from detected user state
    4. Clamp and persist

    Args:
        chip: PersonalityChip for baseline derivation
        user_state: Detected user state (from room_reader)
        intensity: Signal strength multiplier
        persist: Whether to save state to disk

    Returns:
        Updated PAD vector representing current emotional state
    """
    baseline = get_baseline_pad(chip)
    current, _ = _load_state()

    # Decay toward baseline
    current = PADVector(
        pleasure=current.pleasure + (baseline.pleasure - current.pleasure) * _DECAY_RATE,
        arousal=current.arousal + (baseline.arousal - current.arousal) * _DECAY_RATE,
        dominance=current.dominance + (baseline.dominance - current.dominance) * _DECAY_RATE,
    )

    # Apply appraisal from user state
    delta = appraise(user_state, intensity)
    current = PADVector(
        pleasure=current.pleasure + delta.pleasure,
        arousal=current.arousal + delta.arousal,
        dominance=current.dominance + delta.dominance,
    ).clamp()

    if persist:
        _save_state(current)

    return current


def pad_to_primary_emotion(pad: PADVector) -> str:
    """Map a PAD vector to a human-readable primary emotion label.

    Uses nearest-region matching against the emotion map.
    Falls back to 'steady' if no strong match.
    """
    best = "steady"
    best_score = -1.0

    for emotion, min_p, min_a, min_d, threshold in _PAD_TO_EMOTION:
        if pad.pleasure >= min_p and pad.arousal >= min_a and pad.dominance >= min_d:
            # Score = how well the PAD vector fits this region
            score = (
                (pad.pleasure - min_p) * 0.4 +
                (pad.arousal - min_a) * 0.3 +
                (pad.dominance - min_d) * 0.3
            )
            if score > best_score:
                best_score = score
                best = emotion

    return best


def pad_to_mood(pad: PADVector) -> str:
    """Map PAD vector to bridge.v1 mood enum: builder|oracle|zen|chaos."""
    if pad.arousal > 0.1 and pad.dominance > 0.1:
        return "builder"
    if pad.pleasure > 0.1 and pad.arousal < -0.1:
        return "zen"
    if pad.arousal > 0.2 and pad.pleasure > 0.1:
        return "chaos"
    return "oracle"  # Default: thoughtful, measured


def pad_to_intensity(pad: PADVector) -> float:
    """Convert PAD magnitude to a 0-1 intensity value for bridge."""
    magnitude = (abs(pad.pleasure) + abs(pad.arousal) + abs(pad.dominance)) / 3.0
    return round(max(0.1, min(0.9, 0.5 + magnitude)), 2)


def build_emotional_state_for_bridge(
    chip,
    user_state: Optional[str] = None,
    intensity: float = 1.0,
    persist: bool = True,
) -> dict:
    """Build the emotional_state block for bridge.v1 payload.

    This replaces the static emotional_state in bridge.py with a
    dynamic version driven by actual session interactions.

    Returns a dict matching the bridge.v1 emotional_state schema.
    """
    pad = update_emotional_state(chip, user_state, intensity, persist)

    return {
        "mood": pad_to_mood(pad),
        "intensity": pad_to_intensity(pad),
        "continuity_influence": chip.carry_over_weight,
        "primary_emotion": pad_to_primary_emotion(pad),
        "confidence": 0.85,
        "staleness_seconds": 0,
        "pad_vector": pad.to_dict(),
    }


def reset_emotional_state() -> None:
    """Reset emotional state (new session or explicit reset)."""
    if _STATE_FILE.exists():
        try:
            _STATE_FILE.unlink()
        except OSError:
            pass
