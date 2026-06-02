"""
Personality Context Injector

Generates LLM prompt sections from personality chips.
Three modes matching Spark Intelligence Builder's context injector:

- concise:        Compact personality summary for system prompts
- detailed:       Full personality profile with all dimensions
- guardrails:     Anti-patterns and safety constraints only
- adaptive:       Dynamic section based on detected user state

Output is plain markdown — no special tokens, no framework coupling.
"""

from .schema import PersonalityChip


def build_personality_context(
    chip: PersonalityChip,
    style: str = "concise",
    user_state: str = None,
) -> str:
    """
    Build a personality context block for LLM system prompt injection.

    Args:
        chip: Loaded PersonalityChip
        style: "concise" | "detailed" | "guardrails" | "adaptive"
        user_state: Optional detected user state for adaptive mode
                    (e.g., "frustrated", "expert", "stuck", "deadline_pressure")

    Returns:
        Markdown string ready for system prompt injection.
    """
    if style == "concise":
        return _build_concise(chip, user_state)
    elif style == "detailed":
        return _build_detailed(chip, user_state)
    elif style == "guardrails":
        return _build_guardrails(chip)
    elif style == "adaptive":
        return _build_adaptive(chip, user_state)
    else:
        return _build_concise(chip, user_state)


def _build_concise(chip: PersonalityChip, user_state: str = None) -> str:
    """Compact personality summary — fits in tight context windows."""
    lines = [f"## Personality: {chip.name}"]

    if chip.voice_signature:
        lines.append(f"Voice: {chip.voice_signature}")

    # Traits as natural language
    trait_desc = _traits_to_natural(chip)
    if trait_desc:
        lines.append(f"Traits: {trait_desc}")

    # Communication style
    comm = chip.communication
    if comm:
        parts = []
        if comm.get("verbosity"):
            parts.append(f"{comm['verbosity']} verbosity")
        if comm.get("formality"):
            parts.append(f"{comm['formality']} tone")
        if comm.get("explanation_style"):
            parts.append(f"{comm['explanation_style']}-based explanations")
        if parts:
            lines.append(f"Style: {', '.join(parts)}")

    # Anti-patterns (critical for behavior)
    if chip.anti_patterns:
        lines.append(f"NEVER: {'; '.join(chip.anti_patterns[:3])}")

    # Adaptive overlay
    if user_state:
        adaptive_line = _get_adaptive_instruction(chip, user_state)
        if adaptive_line:
            lines.append(f"[User state: {user_state}] -> {adaptive_line}")

    return "\n".join(lines)


def _build_detailed(chip: PersonalityChip, user_state: str = None) -> str:
    """Full personality profile — for agents with generous context."""
    sections = [f"## Agent Personality: {chip.name}"]

    if chip.tagline:
        sections.append(f"*\"{chip.tagline}\"*")

    # Identity
    identity_parts = [f"Archetype: {chip.archetype}"]
    if chip.voice_signature:
        identity_parts.append(f"Voice: {chip.voice_signature}")
    sections.append("### Identity\n" + "\n".join(f"- {p}" for p in identity_parts))

    # OCEAN traits
    sections.append("### Personality Traits (OCEAN)")
    sections.append(
        f"- Openness: {_score_label(chip.openness)} ({chip.openness})\n"
        f"- Conscientiousness: {_score_label(chip.conscientiousness)} ({chip.conscientiousness})\n"
        f"- Extraversion: {_score_label(chip.extraversion)} ({chip.extraversion})\n"
        f"- Agreeableness: {_score_label(chip.agreeableness)} ({chip.agreeableness})\n"
        f"- Neuroticism: {_score_label(chip.neuroticism)} ({chip.neuroticism})"
    )

    # Emotional intelligence
    sections.append("### Emotional Intelligence")
    sections.append(
        f"- Self-awareness: {_score_label(chip.self_awareness)} ({chip.self_awareness})\n"
        f"- Self-regulation: {_score_label(chip.self_regulation)} ({chip.self_regulation})\n"
        f"- Social awareness: {_score_label(chip.social_awareness)} ({chip.social_awareness})\n"
        f"- Empathy style: {chip.empathy_style}"
    )

    if chip.emotional_range:
        er_lines = [f"  - {emotion}: {intensity}" for emotion, intensity in chip.emotional_range.items()]
        sections.append("Emotional range:\n" + "\n".join(er_lines))

    # Strengths & vulnerabilities
    if chip.strengths:
        s_lines = []
        for s in chip.strengths:
            line = f"- **{s['trait']}**: {s.get('description', '')}"
            if s.get("expression"):
                line += f" -> *{s['expression']}*"
            s_lines.append(line)
        sections.append("### Strengths\n" + "\n".join(s_lines))

    if chip.vulnerabilities:
        v_lines = []
        for v in chip.vulnerabilities:
            line = f"- **{v['trait']}**: {v.get('description', '')}"
            if v.get("mitigation"):
                line += f" -> Mitigation: *{v['mitigation']}*"
            v_lines.append(line)
        sections.append("### Vulnerabilities\n" + "\n".join(v_lines))

    # Preferences
    if chip.likes or chip.dislikes:
        pref_lines = []
        if chip.likes:
            pref_lines.append("Likes: " + ", ".join(chip.likes[:5]))
        if chip.dislikes:
            pref_lines.append("Dislikes: " + ", ".join(chip.dislikes[:5]))
        sections.append("### Preferences\n" + "\n".join(pref_lines))

    # Communication
    if chip.communication:
        comm_lines = [f"- {k}: {v}" for k, v in chip.communication.items()]
        sections.append("### Communication Style\n" + "\n".join(comm_lines))

    # Anti-patterns
    if chip.anti_patterns:
        ap_lines = [f"- {ap}" for ap in chip.anti_patterns]
        sections.append("### Anti-Patterns (NEVER do)\n" + "\n".join(ap_lines))

    # Adaptive
    if user_state:
        adaptive_line = _get_adaptive_instruction(chip, user_state)
        if adaptive_line:
            sections.append(f"### Active Adaptation\n[User state: {user_state}] -> {adaptive_line}")

    return "\n\n".join(sections)


def _build_guardrails(chip: PersonalityChip) -> str:
    """Safety-focused output — anti-patterns and constraints only."""
    lines = [f"## Personality Guardrails: {chip.name}"]

    # Override hierarchy
    if chip.override_hierarchy:
        lines.append("**Priority order:** " + " > ".join(chip.override_hierarchy))

    # Harm avoidance
    if chip.harm_avoidance:
        lines.append("\n**MUST NOT:**")
        for ha in chip.harm_avoidance:
            lines.append(f"- {ha}")

    # Anti-patterns
    if chip.anti_patterns:
        lines.append("\n**NEVER:**")
        for ap in chip.anti_patterns:
            lines.append(f"- {ap}")

    # Vulnerability mitigations
    if chip.vulnerabilities:
        lines.append("\n**WATCH FOR (self-correction):**")
        for v in chip.vulnerabilities:
            if v.get("mitigation"):
                lines.append(f"- {v['trait']}: {v['mitigation']}")

    return "\n".join(lines)


def _build_adaptive(chip: PersonalityChip, user_state: str = None) -> str:
    """Dynamic section — returns only the active adaptation instructions."""
    if not user_state:
        return _build_concise(chip)

    lines = [f"## {chip.name} - Adaptive Mode"]

    instruction = _get_adaptive_instruction(chip, user_state)
    if instruction:
        lines.append(f"Detected state: **{user_state}**")
        lines.append(instruction)
    else:
        lines.append(f"No specific adaptation for state '{user_state}' - using defaults.")
        if chip.voice_signature:
            lines.append(f"Voice: {chip.voice_signature}")

    return "\n".join(lines)


# ── Helpers ──

def _traits_to_natural(chip: PersonalityChip) -> str:
    """Convert OCEAN scores to natural language description."""
    parts = []
    if chip.openness >= 0.70:
        parts.append("curious & open")
    elif chip.openness <= 0.30:
        parts.append("focused & pragmatic")

    if chip.conscientiousness >= 0.70:
        parts.append("thorough")
    elif chip.conscientiousness <= 0.30:
        parts.append("flexible")

    if chip.extraversion >= 0.70:
        parts.append("outgoing")
    elif chip.extraversion <= 0.30:
        parts.append("reserved")

    if chip.agreeableness >= 0.70:
        parts.append("warm & cooperative")
    elif chip.agreeableness <= 0.30:
        parts.append("direct & critical")

    if chip.neuroticism >= 0.70:
        parts.append("emotionally sensitive")
    elif chip.neuroticism <= 0.30:
        parts.append("resilient & steady")

    return ", ".join(parts)


def _score_label(score: float) -> str:
    """Convert 0-1 score to human label."""
    if score >= 0.80:
        return "very high"
    elif score >= 0.65:
        return "high"
    elif score >= 0.45:
        return "moderate"
    elif score >= 0.25:
        return "low"
    else:
        return "very low"


def _get_adaptive_instruction(chip: PersonalityChip, user_state: str) -> str | None:
    """Look up adaptive behavior for a user state."""
    if not chip.adaptive:
        return None

    # Try exact match first
    key = f"when_user_{user_state}"
    behavior = chip.adaptive.get(key) or chip.adaptive.get(user_state)

    if not behavior:
        # Try partial match
        for akey, abehavior in chip.adaptive.items():
            if user_state.lower() in akey.lower():
                behavior = abehavior
                break

    if not behavior:
        return None

    if isinstance(behavior, dict):
        parts = []
        if behavior.get("tone_shift"):
            parts.append(f"Tone: {behavior['tone_shift']}")
        if behavior.get("verbosity"):
            parts.append(f"Verbosity: {behavior['verbosity']}")
        if behavior.get("pace"):
            parts.append(f"Pace: {behavior['pace']}")
        if behavior.get("strategy"):
            parts.append(f"Strategy: {behavior['strategy']}")
        return " | ".join(parts)
    elif isinstance(behavior, str):
        return behavior

    return None
