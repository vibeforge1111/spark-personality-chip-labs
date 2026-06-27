"""Tests for personality context injector."""

import pytest
from personality_engine.schema import build_personality, SCHEMA_VERSION
from personality_engine.context import build_personality_context


def _make_chip(**overrides):
    """Build a test chip with optional overrides."""
    spec = {
        "schema": SCHEMA_VERSION,
        "identity": {
            "id": "ctx-test",
            "name": "ContextTest",
            "archetype": "oracle",
            "voice_signature": "calm and clear",
            "tagline": "Test tagline",
        },
        "traits": {
            "openness": 0.85,
            "conscientiousness": 0.70,
            "extraversion": 0.35,
            "agreeableness": 0.65,
            "neuroticism": 0.20,
        },
        "preferences": {
            "communication": {
                "verbosity": "moderate",
                "formality": "professional",
                "explanation_style": "analogy",
            },
        },
        "anti_patterns": [
            "Never dismisses concerns",
            "Never pretends certainty",
        ],
        "adaptive": {
            "when_user_frustrated": {
                "tone_shift": "warmer",
                "strategy": "Acknowledge first",
            },
            "when_user_expert": {
                "tone_shift": "peer",
                "verbosity": "terse",
            },
        },
        "safety": {
            "harm_avoidance": ["No manipulation"],
            "override_hierarchy": ["safety", "user_wellbeing"],
        },
    }
    spec.update(overrides)
    return build_personality(spec)


class TestConcise:

    def test_includes_name(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="concise")
        assert "ContextTest" in ctx

    def test_includes_voice(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="concise")
        assert "calm and clear" in ctx

    def test_includes_traits(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="concise")
        assert "curious" in ctx or "open" in ctx  # High openness

    def test_includes_anti_patterns(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="concise")
        assert "NEVER" in ctx

    def test_includes_style(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="concise")
        assert "moderate" in ctx or "professional" in ctx

    def test_adaptive_with_user_state(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="concise", user_state="frustrated")
        assert "frustrated" in ctx.lower()
        assert "warmer" in ctx.lower() or "acknowledge" in ctx.lower()


class TestDetailed:

    def test_includes_all_sections(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="detailed")
        assert "OCEAN" in ctx or "Personality Traits" in ctx
        assert "Emotional Intelligence" in ctx
        assert "Anti-Pattern" in ctx

    def test_includes_tagline(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="detailed")
        assert "Test tagline" in ctx

    def test_trait_labels(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="detailed")
        assert "0.85" in ctx  # openness value
        assert "high" in ctx.lower()  # label for 0.85


class TestGuardrails:

    def test_includes_harm_avoidance(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="guardrails")
        assert "No manipulation" in ctx

    def test_includes_anti_patterns(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="guardrails")
        assert "NEVER" in ctx

    def test_includes_priority_order(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="guardrails")
        assert "safety" in ctx.lower()

    def test_no_trait_details(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="guardrails")
        # Guardrails mode should NOT include OCEAN scores
        assert "0.85" not in ctx


class TestAdaptive:

    def test_with_known_state(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="adaptive", user_state="frustrated")
        assert "frustrated" in ctx.lower()

    def test_with_unknown_state(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="adaptive", user_state="bored")
        assert "no specific adaptation" in ctx.lower() or "defaults" in ctx.lower()

    def test_unknown_state_omits_empty_voice_line(self):
        chip = _make_chip(identity={"id": "ctx-test", "name": "ContextTest", "voice_signature": ""})
        ctx = build_personality_context(chip, style="adaptive", user_state="bored")
        assert "Voice:" not in ctx
        assert not ctx.endswith("\n")

    def test_without_state_falls_back(self):
        chip = _make_chip()
        ctx = build_personality_context(chip, style="adaptive")
        # Should fall back to concise
        assert "ContextTest" in ctx


class TestUnknownStyleWarning:

    def test_unknown_style_emits_warning(self):
        chip = _make_chip()
        with pytest.warns(UserWarning, match="Unknown context style 'compact'"):
            ctx = build_personality_context(chip, style="compact")
        # Still returns valid output (falls back to concise)
        assert "ContextTest" in ctx

    def test_unknown_style_returns_concise_output(self):
        chip = _make_chip()
        with pytest.warns(UserWarning):
            unknown_ctx = build_personality_context(chip, style="compact")
        concise_ctx = build_personality_context(chip, style="concise")
        assert unknown_ctx == concise_ctx

    def test_known_styles_do_not_warn(self):
        chip = _make_chip()
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            for style in ("concise", "detailed", "guardrails", "adaptive"):
                build_personality_context(chip, style=style)
