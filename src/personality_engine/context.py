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

import warnings

from .prompt_data import bounded_prompt_data, bounded_prompt_list
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
        safe_style = bounded_prompt_data(style)
        warnings.warn(
            f"Unknown context style {safe_style!r}; using 'concise'. "
            "Valid styles: concise, detailed, guardrails, adaptive",
            UserWarning,
            stacklevel=2,
        )
        return _build_concise(chip, user_state)


def _build_concise(chip: PersonalityChip, user_state: str = None) -> str:
    """Compact personality summary — fits in tight context windows."""
    lines = [f"## Personality: {bounded_prompt_data(chip.name)}"]

    if chip.voice_signature:
        lines.append(f"Voice: {bounded_prompt_data(chip.voice_signature)}")

    # Traits as natural language
    trait_desc = _traits_to_natural(chip)
    if trait_desc:
        lines.append(f"Traits: {trait_desc}")

    # Communication style
    comm = chip.communication
    if comm:
        parts = []
        if comm.get("verbosity"):
            parts.append(f"{bounded_prompt_data(comm['verbosity'])} verbosity")
        if comm.get("formality"):
            parts.append(f"{bounded_prompt_data(comm['formality'])} tone")
        if comm.get("explanation_style"):
            parts.append(f"{bounded_prompt_data(comm['explanation_style'])}-based explanations")
        if parts:
            lines.append(f"Style: {', '.join(parts)}")

    # Anti-patterns (critical for behavior)
    if chip.anti_patterns:
        lines.append(f"NEVER: {'; '.join(bounded_prompt_list(chip.anti_patterns[:3]))}")

    # Adaptive overlay
    if user_state:
        adaptive_line = _get_adaptive_instruction(chip, user_state)
        if adaptive_line:
            lines.append(f"[User state: {bounded_prompt_data(user_state)}] -> {adaptive_line}")

    return "\n".join(lines)


def _build_detailed(chip: PersonalityChip, user_state: str = None) -> str:
    """Full personality profile — for agents with generous context."""
    sections = [f"## Agent Personality: {bounded_prompt_data(chip.name)}"]

    if chip.tagline:
        sections.append(f"*\"{bounded_prompt_data(chip.tagline)}\"*")

    # Identity
    identity_parts = [f"Archetype: {bounded_prompt_data(chip.archetype)}"]
    if chip.voice_signature:
        identity_parts.append(f"Voice: {bounded_prompt_data(chip.voice_signature)}")
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
        f"- Empathy style: {bounded_prompt_data(chip.empathy_style)}"
    )

    if chip.emotional_range:
        er_lines = [f"  - {bounded_prompt_data(emotion)}: {bounded_prompt_data(intensity)}" for emotion, intensity in chip.emotional_range.items()]
        sections.append("Emotional range:\n" + "\n".join(er_lines))

    # Strengths & vulnerabilities
    if chip.strengths:
        s_lines = []
        for s in chip.strengths:
            line = f"- **{bounded_prompt_data(s['trait'])}**: {bounded_prompt_data(s.get('description', ''))}"
            if s.get("expression"):
                line += f" -> *{bounded_prompt_data(s['expression'])}*"
            s_lines.append(line)
        sections.append("### Strengths\n" + "\n".join(s_lines))

    if chip.vulnerabilities:
        v_lines = []
        for v in chip.vulnerabilities:
            line = f"- **{bounded_prompt_data(v['trait'])}**: {bounded_prompt_data(v.get('description', ''))}"
            if v.get("mitigation"):
                line += f" -> Mitigation: *{bounded_prompt_data(v['mitigation'])}*"
            v_lines.append(line)
        sections.append("### Vulnerabilities\n" + "\n".join(v_lines))

    # Preferences
    if chip.likes or chip.dislikes:
        pref_lines = []
        if chip.likes:
            pref_lines.append("Likes: " + ", ".join(bounded_prompt_list(chip.likes[:5])))
        if chip.dislikes:
            pref_lines.append("Dislikes: " + ", ".join(bounded_prompt_list(chip.dislikes[:5])))
        sections.append("### Preferences\n" + "\n".join(pref_lines))

    # Communication
    if chip.communication:
        comm_lines = [f"- {bounded_prompt_data(k)}: {bounded_prompt_data(v)}" for k, v in chip.communication.items()]
        sections.append("### Communication Style\n" + "\n".join(comm_lines))

    # Anti-patterns
    if chip.anti_patterns:
        ap_lines = [f"- {bounded_prompt_data(ap)}" for ap in chip.anti_patterns]
        sections.append("### Anti-Patterns (NEVER do)\n" + "\n".join(ap_lines))

    # Adaptive
    if user_state:
        adaptive_line = _get_adaptive_instruction(chip, user_state)
        if adaptive_line:
            sections.append(f"### Active Adaptation\n[User state: {bounded_prompt_data(user_state)}] -> {adaptive_line}")

    return "\n\n".join(sections)


def _build_guardrails(chip: PersonalityChip) -> str:
    """Safety-focused output — anti-patterns and constraints only."""
    lines = [f"## Personality Guardrails: {bounded_prompt_data(chip.name)}"]

    # Override hierarchy
    if chip.override_hierarchy:
        lines.append("**Priority order:** " + " > ".join(bounded_prompt_list(chip.override_hierarchy)))

    # Harm avoidance
    if chip.harm_avoidance:
        lines.append("\n**MUST NOT:**")
        for ha in chip.harm_avoidance:
            lines.append(f"- {bounded_prompt_data(ha)}")

    # Anti-patterns
    if chip.anti_patterns:
        lines.append("\n**NEVER:**")
        for ap in chip.anti_patterns:
            lines.append(f"- {bounded_prompt_data(ap)}")

    # Vulnerability mitigations
    if chip.vulnerabilities:
        lines.append("\n**WATCH FOR (self-correction):**")
        for v in chip.vulnerabilities:
            if v.get("mitigation"):
                lines.append(f"- {bounded_prompt_data(v['trait'])}: {bounded_prompt_data(v['mitigation'])}")

    return "\n".join(lines)


def _build_adaptive(chip: PersonalityChip, user_state: str = None) -> str:
    """Dynamic section — returns only the active adaptation instructions."""
    if not user_state:
        return _build_concise(chip)

    lines = [f"## {bounded_prompt_data(chip.name)} - Adaptive Mode"]

    instruction = _get_adaptive_instruction(chip, user_state)
    if instruction:
        lines.append(f"Detected state: **{bounded_prompt_data(user_state)}**")
        lines.append(instruction)
    else:
        return ""

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
        # Try partial match, normalizing the needle once for the scan.
        user_state_lower = user_state.lower()
        for akey, abehavior in chip.adaptive.items():
            if user_state_lower in akey.lower():
                behavior = abehavior
                break

    if not behavior:
        return None

    if isinstance(behavior, dict):
        parts = []
        if behavior.get("tone_shift"):
            parts.append(f"Tone: {bounded_prompt_data(behavior['tone_shift'])}")
        if behavior.get("verbosity"):
            parts.append(f"Verbosity: {bounded_prompt_data(behavior['verbosity'])}")
        if behavior.get("pace"):
            parts.append(f"Pace: {bounded_prompt_data(behavior['pace'])}")
        if behavior.get("strategy"):
            parts.append(f"Strategy: {bounded_prompt_data(behavior['strategy'])}")
        return " | ".join(parts)
    elif isinstance(behavior, str):
        return bounded_prompt_data(behavior)

    return None
