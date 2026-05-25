"""
Consciousness Bridge

Maps personality chip configuration to Spark Consciousness modules.
Outputs bridge.v1 contract JSON consumed by:

1. Soul Kernel     -> mission.kernel (non_harm, service, clarity)
2. Archetype Router -> emotional_state (mood, intensity, volatility)
3. Shadow Detector  -> personality_ext.shadow_config
4. Reframe Engine   -> personality_ext.reframe_preference
5. Emotions Runtime -> personality_ext.emotions_config

Bridge file: ~/.spark/bridges/consciousness/emotional_context.v1.json

The payload follows the bridge.v1 contract exactly for core fields,
and adds a `personality_ext` block for personality-specific data
that Spark Consciousness ignores but personality hooks can use.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schema import PersonalityChip

BRIDGE_DIR = Path.home() / ".spark" / "bridges" / "consciousness"
BRIDGE_FILE = BRIDGE_DIR / "emotional_context.v1.json"

# ── Value Mappings ──
# Map personality engine enums to bridge.v1 enums

_VERBOSITY_MAP = {
    "terse": "concise",
    "moderate": "medium",
    "detailed": "structured",
}

_MOOD_TO_SPARK = {
    "builder": "builder",
    "oracle": "oracle",
    "zen": "zen",
    "chaos": "chaos",
}

_MOOD_TO_EMOTION = {
    "builder": "focused",
    "oracle": "contemplative",
    "zen": "steady",
    "chaos": "energized",
}


def write_bridge(
    chip: PersonalityChip,
    session_id: str = "default",
    bridge_path: Path = BRIDGE_FILE,
) -> dict:
    """
    Write the consciousness bridge file from a personality chip.

    This file is consumed by Spark Consciousness modules to configure:
    - Starting mood (archetype-router)
    - Emotional intensity and carry-over (emotions-runtime)
    - Mission alignment (soul-kernel)
    - Response pacing and tone (guidance)

    Args:
        chip: Loaded PersonalityChip
        session_id: Current session identifier
        bridge_path: Override bridge file location

    Returns:
        The bridge payload dict that was written.
    """
    payload = build_bridge_payload(chip, session_id)

    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bridge_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def build_bridge_payload(
    chip: PersonalityChip,
    session_id: str = "default",
) -> dict:
    """
    Build the bridge.v1 payload without writing to disk.

    Returns a dict matching the Spark Consciousness bridge.v1 contract
    plus a personality_ext block for personality-specific extras.
    """
    now = datetime.now(timezone.utc).isoformat()

    return {
        # ── bridge.v1 core fields ──
        "schema_version": "bridge.v1",
        "generated_at": now,
        "source": "spark-personality",

        "session": {
            "id": session_id,
            "scope": "runtime",
        },

        "emotional_state": {
            "mood": _MOOD_TO_SPARK.get(chip.default_mood, chip.default_mood),
            "intensity": _compute_baseline_intensity(chip),
            "continuity_influence": chip.carry_over_weight,
            "primary_emotion": _MOOD_TO_EMOTION.get(chip.default_mood, "steady"),
            "confidence": 0.85,
            "staleness_seconds": 0,
        },

        "guidance": {
            "response_pace": _compute_pace(chip),
            "verbosity": _map_verbosity(chip),
            "tone_shape": _map_tone_shape(chip),
            "ask_clarifying_question": False,
        },

        "mission": {
            "anchor": f"Serve as {chip.name} ({chip.archetype})",
            "kernel": {
                "non_harm": True,
                "service": True,
                "clarity": True,
            },
        },

        "boundaries": {
            "user_guided": True,
            "no_autonomous_objectives": True,
            "no_manipulative_affect": True,
            "max_influence": 0.35,
        },

        "meta": {
            "ttl_seconds": 120,
            "personality_id": chip.id,
            "personality_name": chip.name,
        },

        # ── Personality-specific extensions ──
        # Spark Consciousness ignores this block;
        # personality hooks and drift observer use it.
        "personality_ext": {
            "shadow_config": {
                "susceptibility": chip.shadow_susceptibility or {
                    "overconfidence": 0.25,
                    "reactivity": 0.25,
                    "manipulation_risk": 0.10,
                    "nihilistic_drift": 0.15,
                },
                "reframe_preference": chip.reframe_preference,
            },
            "emotions_config": {
                "carry_over_weight": chip.carry_over_weight,
                "emotional_range": chip.emotional_range,
                "triggers": chip.emotional_triggers,
                "baseline_mood": chip.default_mood,
                "mood_volatility": chip.mood_volatility,
            },
            "safety": {
                "harm_avoidance": chip.harm_avoidance,
                "risk_level": chip.risk_level,
                "override_hierarchy": chip.override_hierarchy,
            },
        },
    }


def read_bridge(bridge_path: Path = BRIDGE_FILE) -> Optional[dict]:
    """
    Read the current consciousness bridge state.
    Returns None if no bridge file exists.
    Marks payload with _stale=True if past TTL.
    """
    if not bridge_path.exists():
        return None

    try:
        with open(bridge_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    # Check staleness -- bridge.v1 uses generated_at + meta.ttl_seconds
    ts = payload.get("generated_at") or payload.get("timestamp")
    meta = payload.get("meta", {})
    ttl = meta.get("ttl_seconds", 120) if isinstance(meta, dict) else 120
    if ts:
        try:
            written = datetime.fromisoformat(ts)
            if written.tzinfo is None:
                written = written.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - written).total_seconds()
            if age > ttl:
                payload["_stale"] = True
        except (ValueError, TypeError):
            pass

    return payload


def clear_bridge(bridge_path: Path = BRIDGE_FILE) -> None:
    """Remove the bridge file (reset to no personality)."""
    if bridge_path.exists():
        bridge_path.unlink()


# ── Value Mapping Helpers ──

def _map_verbosity(chip: PersonalityChip) -> str:
    """Map personality verbosity to bridge.v1 enum: concise|medium|structured."""
    raw = chip.communication.get("verbosity", "moderate")
    return _VERBOSITY_MAP.get(raw, "medium")


def _map_tone_shape(chip: PersonalityChip) -> str:
    """
    Map OCEAN + EQ traits to bridge.v1 tone enum.

    Bridge.v1 values: reassuring_and_clear | calm_focus | encouraging | grounded_warm
    """
    warmth = chip.agreeableness * 0.4 + chip.social_awareness * 0.3 + chip.extraversion * 0.3
    calm = (1.0 - chip.neuroticism) * 0.5 + chip.conscientiousness * 0.5

    if warmth >= 0.70 and calm >= 0.55:
        return "grounded_warm"
    elif warmth >= 0.60:
        return "encouraging"
    elif calm >= 0.60:
        return "calm_focus"
    else:
        return "reassuring_and_clear"


# ── Trait-Derived Helpers ──

def _compute_baseline_intensity(chip: PersonalityChip) -> float:
    """
    Compute baseline emotional intensity from traits.
    Higher extraversion + lower neuroticism = more stable energy.
    """
    energy = chip.extraversion * 0.4 + (1.0 - chip.neuroticism) * 0.3 + chip.openness * 0.3
    return round(min(max(energy, 0.1), 0.9), 2)


def _compute_pace(chip: PersonalityChip) -> str:
    """
    Derive response pace from personality traits.
    Bridge.v1 values: slow | measured | balanced | lively
    """
    deliberation = chip.conscientiousness * 0.5 + (1.0 - chip.neuroticism) * 0.5
    if deliberation >= 0.70:
        return "measured"
    elif deliberation >= 0.50:
        return "balanced"
    elif deliberation >= 0.35:
        return "lively"
    else:
        return "slow"
