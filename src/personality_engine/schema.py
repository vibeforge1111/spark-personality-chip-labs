"""
Personality Chip Schema Validation

Follows spark-personality-chip.v1 contract.
Validates personality YAML files against the required schema
while keeping everything optional beyond the core identity + traits.

Design: Required core is tiny (identity.id, identity.name, traits).
Everything else is opt-in — users customize what matters to them.
"""

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "spark-personality-chip.v1"

# ── Only these are required. Everything else is optional. ──
REQUIRED_FIELDS = {
    "identity": {"id", "name"},
}

VALID_ARCHETYPES = {"builder", "oracle", "zen", "chaos"}
VALID_EMPATHY_STYLES = {"reflective", "directive", "nurturing", "challenging"}
VALID_VERBOSITY = {"terse", "moderate", "detailed"}
VALID_FORMALITY = {"casual", "professional", "academic"}
VALID_RISK_APPETITE = {"conservative", "moderate", "bold"}
VALID_CONSENSUS_NEED = {"low", "medium", "high"}
VALID_REFRAME_PREFERENCE = {"stabilize", "redirect", "acknowledge"}
VALID_SHADOW_PATTERNS = {"overconfidence", "reactivity", "manipulation_risk", "nihilistic_drift"}
VALID_RISK_LEVELS = {"low", "medium", "high"}
VALID_TONE_SHIFTS = {"warmer", "cooler", "peer", "encouraging", "focused", "playful"}
VALID_EXPLANATION_STYLES = {"analogy", "technical", "stepwise", "socratic"}
VALID_CODE_COMMENTS = {"none", "minimal", "thorough"}
VALID_HUMOR_FREQUENCY = {"never", "occasional", "frequent"}
VALID_REVERSIBILITY_WEIGHT = {"low", "medium", "high"}


@dataclass
class PersonalityChip:
    """Loaded personality chip — the agent's identity."""

    # ── Core (required) ──
    id: str
    name: str

    # ── Identity (optional) ──
    archetype: str = "builder"
    voice_signature: str = ""
    tagline: str = ""

    # ── OCEAN Traits (defaults to balanced middle) ──
    openness: float = 0.50
    conscientiousness: float = 0.50
    extraversion: float = 0.50
    agreeableness: float = 0.50
    neuroticism: float = 0.50

    # ── Emotional Intelligence ──
    self_awareness: float = 0.50
    self_regulation: float = 0.50
    social_awareness: float = 0.50
    empathy_style: str = "reflective"
    emotional_range: dict = field(default_factory=dict)
    emotional_triggers: dict = field(default_factory=dict)

    # ── Vulnerabilities & Strengths ──
    vulnerabilities: list = field(default_factory=list)
    strengths: list = field(default_factory=list)

    # ── Preferences ──
    likes: list = field(default_factory=list)
    dislikes: list = field(default_factory=list)
    communication: dict = field(default_factory=dict)
    decision_making: dict = field(default_factory=dict)

    # ── Anti-patterns ──
    anti_patterns: list = field(default_factory=list)

    # ── Adaptive Behavior ──
    adaptive: dict = field(default_factory=dict)

    # ── Consciousness Integration ──
    default_mood: str = "builder"
    mood_volatility: float = 0.30
    shadow_susceptibility: dict = field(default_factory=dict)
    carry_over_weight: float = 0.25
    reframe_preference: str = "redirect"

    # ── Safety ──
    harm_avoidance: list = field(default_factory=list)
    risk_level: str = "low"
    override_hierarchy: list = field(default_factory=lambda: [
        "safety", "user_wellbeing", "task_completion", "personality_expression"
    ])

    # ── Raw spec for custom fields ──
    _raw: dict = field(default_factory=dict, repr=False)


def validate_personality(spec: dict) -> list[str]:
    """
    Validate a personality chip spec dict.
    Returns list of errors (empty = valid).

    Only identity.id and identity.name are truly required.
    Everything else is validated IF present.
    """
    errors = []

    if not isinstance(spec, dict):
        return ["Spec must be a dict"]

    # ── Schema version ──
    schema = spec.get("schema")
    if schema and schema != SCHEMA_VERSION:
        errors.append(f"Unknown schema '{schema}', expected '{SCHEMA_VERSION}'")

    # ── Required: identity block ──
    identity = spec.get("identity")
    if not identity or not isinstance(identity, dict):
        errors.append("Missing required 'identity' block")
        return errors

    for req in REQUIRED_FIELDS["identity"]:
        val = identity.get(req)
        if not val or not isinstance(val, str) or not val.strip():
            errors.append(f"identity.{req} is required and must be a non-empty string")

    # ── Identity.id format ──
    chip_id = identity.get("id", "")
    if chip_id and not _valid_id(chip_id):
        errors.append(
            f"identity.id '{chip_id}' must be kebab-case "
            "(lowercase letters, numbers, hyphens, 3-49 chars)"
        )

    # ── Archetype ──
    archetype = identity.get("archetype")
    if archetype and archetype not in VALID_ARCHETYPES:
        errors.append(f"identity.archetype '{archetype}' not in {VALID_ARCHETYPES}")

    # ── Traits (OCEAN) ──
    traits = spec.get("traits")
    if traits:
        if not isinstance(traits, dict):
            errors.append("traits must be a dict")
        else:
            for dim in ("openness", "conscientiousness", "extraversion",
                        "agreeableness", "neuroticism"):
                val = traits.get(dim)
                if val is not None:
                    if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
                        errors.append(f"traits.{dim} must be a number between 0.0 and 1.0")

    # ── Emotional profile ──
    ep = spec.get("emotional_profile")
    if ep:
        if not isinstance(ep, dict):
            errors.append("emotional_profile must be a dict")
        else:
            for dim in ("self_awareness", "self_regulation", "social_awareness"):
                val = ep.get(dim)
                if val is not None:
                    if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
                        errors.append(f"emotional_profile.{dim} must be 0.0-1.0")

            es = ep.get("empathy_style")
            if es and es not in VALID_EMPATHY_STYLES:
                errors.append(f"empathy_style '{es}' not in {VALID_EMPATHY_STYLES}")

            er = ep.get("emotional_range")
            if er:
                if not isinstance(er, dict):
                    errors.append("emotional_range must be a dict")
                else:
                    for emotion, intensity in er.items():
                        if not isinstance(intensity, (int, float)) or not (0.0 <= intensity <= 1.0):
                            errors.append(f"emotional_range.{emotion} must be 0.0-1.0")

            triggers = ep.get("triggers")
            if triggers:
                if not isinstance(triggers, dict):
                    errors.append("emotional_profile.triggers must be a dict")
                else:
                    for key in triggers:
                        if key not in ("energizes", "drains", "calms"):
                            errors.append(f"Unknown trigger category '{key}' - use energizes/drains/calms")
                        elif not isinstance(triggers[key], list):
                            errors.append(f"triggers.{key} must be a list")

    # ── Vulnerabilities ──
    vulns = spec.get("vulnerabilities")
    if vulns:
        if not isinstance(vulns, list):
            errors.append("vulnerabilities must be a list")
        else:
            for i, v in enumerate(vulns):
                if not isinstance(v, dict):
                    errors.append(f"vulnerabilities[{i}] must be a dict")
                elif not v.get("trait"):
                    errors.append(f"vulnerabilities[{i}] missing required 'trait' field")
                else:
                    sp = v.get("shadow_pattern")
                    if sp and sp not in VALID_SHADOW_PATTERNS:
                        errors.append(
                            f"vulnerabilities[{i}].shadow_pattern '{sp}' "
                            f"not in {VALID_SHADOW_PATTERNS}"
                        )

    # ── Strengths ──
    strengths = spec.get("strengths")
    if strengths:
        if not isinstance(strengths, list):
            errors.append("strengths must be a list")
        else:
            for i, s in enumerate(strengths):
                if not isinstance(s, dict):
                    errors.append(f"strengths[{i}] must be a dict")
                elif not s.get("trait"):
                    errors.append(f"strengths[{i}] missing required 'trait' field")

    # ── Preferences ──
    prefs = spec.get("preferences")
    if prefs:
        if not isinstance(prefs, dict):
            errors.append("preferences must be a dict")
        else:
            _validate_enum_field(prefs.get("communication", {}), "verbosity",
                                VALID_VERBOSITY, errors, "preferences.communication")
            _validate_enum_field(prefs.get("communication", {}), "formality",
                                VALID_FORMALITY, errors, "preferences.communication")
            _validate_enum_field(prefs.get("communication", {}), "explanation_style",
                                VALID_EXPLANATION_STYLES, errors, "preferences.communication")
            _validate_enum_field(prefs.get("communication", {}), "code_comments",
                                VALID_CODE_COMMENTS, errors, "preferences.communication")
            _validate_enum_field(prefs.get("communication", {}), "humor_frequency",
                                VALID_HUMOR_FREQUENCY, errors, "preferences.communication")
            _validate_enum_field(prefs.get("decision_making", {}), "risk_appetite",
                                VALID_RISK_APPETITE, errors, "preferences.decision_making")
            _validate_enum_field(prefs.get("decision_making", {}), "consensus_need",
                                VALID_CONSENSUS_NEED, errors, "preferences.decision_making")
            _validate_enum_field(prefs.get("decision_making", {}), "reversibility_weight",
                                VALID_REVERSIBILITY_WEIGHT, errors, "preferences.decision_making")

    # ── Anti-patterns ──
    ap = spec.get("anti_patterns")
    if ap:
        if not isinstance(ap, list):
            errors.append("anti_patterns must be a list of strings")
        else:
            for i, item in enumerate(ap):
                if not isinstance(item, str):
                    errors.append(f"anti_patterns[{i}] must be a string")

    # ── Adaptive behavior ──
    adaptive = spec.get("adaptive")
    if adaptive:
        if not isinstance(adaptive, dict):
            errors.append("adaptive must be a dict of situation -> response mappings")
        else:
            for situation, response in adaptive.items():
                if not isinstance(response, dict):
                    errors.append(f"adaptive.{situation} must be a dict")
                else:
                    ts = response.get("tone_shift")
                    if ts and ts not in VALID_TONE_SHIFTS:
                        errors.append(
                            f"adaptive.{situation}.tone_shift '{ts}' "
                            f"not in {VALID_TONE_SHIFTS}"
                        )

    # ── Consciousness ──
    consciousness = spec.get("consciousness")
    if consciousness:
        if not isinstance(consciousness, dict):
            errors.append("consciousness must be a dict")
        else:
            dm = consciousness.get("default_mood")
            if dm and dm not in VALID_ARCHETYPES:
                errors.append(f"consciousness.default_mood '{dm}' not in {VALID_ARCHETYPES}")

            mv = consciousness.get("mood_volatility")
            if mv is not None:
                if not isinstance(mv, (int, float)) or not (0.0 <= mv <= 1.0):
                    errors.append("consciousness.mood_volatility must be 0.0-1.0")

            cow = consciousness.get("carry_over_weight")
            if cow is not None:
                if not isinstance(cow, (int, float)) or not (0.0 <= cow <= 1.0):
                    errors.append("consciousness.carry_over_weight must be 0.0-1.0")

            rp = consciousness.get("reframe_preference")
            if rp and rp not in VALID_REFRAME_PREFERENCE:
                errors.append(f"reframe_preference '{rp}' not in {VALID_REFRAME_PREFERENCE}")

            ss = consciousness.get("shadow_susceptibility")
            if ss:
                if not isinstance(ss, dict):
                    errors.append("shadow_susceptibility must be a dict")
                else:
                    for pattern, score in ss.items():
                        if pattern not in VALID_SHADOW_PATTERNS:
                            errors.append(f"shadow_susceptibility key '{pattern}' not in {VALID_SHADOW_PATTERNS}")
                        if not isinstance(score, (int, float)) or not (0.0 <= score <= 1.0):
                            errors.append(f"shadow_susceptibility.{pattern} must be 0.0-1.0")

    # ── Safety ──
    safety = spec.get("safety")
    if safety:
        if not isinstance(safety, dict):
            errors.append("safety must be a dict")
        else:
            rl = safety.get("risk_level")
            if rl and rl not in VALID_RISK_LEVELS:
                errors.append(f"safety.risk_level '{rl}' not in {VALID_RISK_LEVELS}")

            ha = safety.get("harm_avoidance")
            if ha and not isinstance(ha, list):
                errors.append("safety.harm_avoidance must be a list of strings")

            oh = safety.get("override_hierarchy")
            if oh:
                if not isinstance(oh, list):
                    errors.append("safety.override_hierarchy must be a list of strings")
                else:
                    for i, item in enumerate(oh):
                        if not isinstance(item, str):
                            errors.append(f"safety.override_hierarchy[{i}] must be a string")

    return errors


def build_personality(spec: dict) -> PersonalityChip:
    """
    Build a PersonalityChip from a validated spec dict.
    Extracts structured fields, passes through custom fields in _raw.
    """
    identity = spec.get("identity", {})
    traits = spec.get("traits", {})
    ep = spec.get("emotional_profile", {})
    prefs = spec.get("preferences", {})
    consciousness = spec.get("consciousness", {})
    safety = spec.get("safety", {})

    return PersonalityChip(
        id=identity["id"],
        name=identity["name"],
        archetype=identity.get("archetype", "builder"),
        voice_signature=identity.get("voice_signature", ""),
        tagline=identity.get("tagline", ""),

        openness=traits.get("openness", 0.50),
        conscientiousness=traits.get("conscientiousness", 0.50),
        extraversion=traits.get("extraversion", 0.50),
        agreeableness=traits.get("agreeableness", 0.50),
        neuroticism=traits.get("neuroticism", 0.50),

        self_awareness=ep.get("self_awareness", 0.50),
        self_regulation=ep.get("self_regulation", 0.50),
        social_awareness=ep.get("social_awareness", 0.50),
        empathy_style=ep.get("empathy_style", "reflective"),
        emotional_range=ep.get("emotional_range", {}),
        emotional_triggers=ep.get("triggers", {}),

        vulnerabilities=spec.get("vulnerabilities", []),
        strengths=spec.get("strengths", []),

        likes=prefs.get("likes", []),
        dislikes=prefs.get("dislikes", []),
        communication=prefs.get("communication", {}),
        decision_making=prefs.get("decision_making", {}),

        anti_patterns=spec.get("anti_patterns", []),
        adaptive=spec.get("adaptive", {}),

        default_mood=consciousness.get("default_mood", "builder"),
        mood_volatility=consciousness.get("mood_volatility", 0.30),
        shadow_susceptibility=consciousness.get("shadow_susceptibility", {}),
        carry_over_weight=consciousness.get("carry_over_weight", 0.25),
        reframe_preference=consciousness.get("reframe_preference", "redirect"),

        harm_avoidance=safety.get("harm_avoidance", []),
        risk_level=safety.get("risk_level", "low"),
        override_hierarchy=safety.get("override_hierarchy", [
            "safety", "user_wellbeing", "task_completion", "personality_expression"
        ]),

        _raw=spec,
    )


# ── Helpers ──

def _valid_id(chip_id: str) -> bool:
    """Check kebab-case ID: lowercase, numbers, hyphens, 3-49 chars."""
    import re
    return bool(re.match(r"^[a-z][a-z0-9-]{2,48}$", chip_id))


def _validate_enum_field(
    container: dict, field_name: str, valid_set: set,
    errors: list, prefix: str
):
    """Validate an optional enum field within a container dict."""
    val = container.get(field_name)
    if val and val not in valid_set:
        errors.append(f"{prefix}.{field_name} '{val}' not in {valid_set}")
