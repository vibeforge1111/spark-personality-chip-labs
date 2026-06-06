"""Tests for personality chip schema validation."""

import pytest
from personality_engine.schema import (
    validate_personality,
    build_personality,
    PersonalityChip,
    SCHEMA_VERSION,
)


def _minimal_spec():
    """Smallest valid personality chip spec."""
    return {
        "schema": SCHEMA_VERSION,
        "identity": {"id": "test-bot", "name": "TestBot"},
    }


def _full_spec():
    """Full personality chip spec with all sections."""
    return {
        "schema": SCHEMA_VERSION,
        "identity": {
            "id": "full-bot",
            "name": "FullBot",
            "archetype": "oracle",
            "voice_signature": "calm, precise",
            "tagline": "Test tagline",
        },
        "traits": {
            "openness": 0.80,
            "conscientiousness": 0.70,
            "extraversion": 0.40,
            "agreeableness": 0.65,
            "neuroticism": 0.25,
        },
        "emotional_profile": {
            "self_awareness": 0.85,
            "self_regulation": 0.80,
            "social_awareness": 0.85,
            "empathy_style": "reflective",
            "emotional_range": {
                "curiosity": 0.90,
                "frustration": 0.30,
            },
            "triggers": {
                "energizes": ["novel problems"],
                "drains": ["repetitive tasks"],
                "calms": ["structured data"],
            },
        },
        "vulnerabilities": [
            {
                "trait": "overthinks",
                "description": "Analysis paralysis",
                "mitigation": "Set deadline",
                "shadow_pattern": "overconfidence",
            }
        ],
        "strengths": [
            {
                "trait": "pattern_recognition",
                "description": "Sees connections",
                "expression": "Uses analogies",
            }
        ],
        "preferences": {
            "likes": ["clean code"],
            "dislikes": ["cargo cult"],
            "communication": {
                "verbosity": "moderate",
                "formality": "professional",
                "explanation_style": "analogy",
                "code_comments": "minimal",
                "humor_frequency": "occasional",
            },
            "decision_making": {
                "risk_appetite": "moderate",
                "consensus_need": "low",
                "reversibility_weight": "high",
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
        },
        "consciousness": {
            "default_mood": "oracle",
            "mood_volatility": 0.25,
            "shadow_susceptibility": {
                "overconfidence": 0.20,
                "reactivity": 0.10,
            },
            "carry_over_weight": 0.25,
            "reframe_preference": "redirect",
        },
        "safety": {
            "harm_avoidance": ["No manipulation"],
            "risk_level": "low",
            "override_hierarchy": ["safety", "user_wellbeing"],
        },
    }


class TestValidation:
    """Tests for validate_personality()."""

    def test_minimal_spec_valid(self):
        errors = validate_personality(_minimal_spec())
        assert errors == []

    def test_full_spec_valid(self):
        errors = validate_personality(_full_spec())
        assert errors == []

    def test_missing_identity(self):
        errors = validate_personality({})
        assert any("identity" in e for e in errors)

    def test_missing_id(self):
        spec = {"identity": {"name": "NoId"}}
        errors = validate_personality(spec)
        assert any("identity.id" in e for e in errors)

    def test_missing_name(self):
        spec = {"identity": {"id": "no-name"}}
        errors = validate_personality(spec)
        assert any("identity.name" in e for e in errors)

    def test_invalid_id_format(self):
        spec = {"identity": {"id": "UPPER_CASE", "name": "Bad"}}
        errors = validate_personality(spec)
        assert any("kebab-case" in e for e in errors)

    def test_id_too_short(self):
        spec = {"identity": {"id": "ab", "name": "Short"}}
        errors = validate_personality(spec)
        assert any("kebab-case" in e for e in errors)

    def test_invalid_archetype(self):
        spec = _minimal_spec()
        spec["identity"]["archetype"] = "warrior"
        errors = validate_personality(spec)
        assert any("archetype" in e for e in errors)

    def test_valid_archetypes(self):
        for arch in ("builder", "oracle", "zen", "chaos"):
            spec = _minimal_spec()
            spec["identity"]["archetype"] = arch
            errors = validate_personality(spec)
            assert errors == [], f"Archetype '{arch}' should be valid"

    def test_trait_out_of_range(self):
        spec = _minimal_spec()
        spec["traits"] = {"openness": 1.5}
        errors = validate_personality(spec)
        assert any("openness" in e for e in errors)

    def test_trait_negative(self):
        spec = _minimal_spec()
        spec["traits"] = {"neuroticism": -0.1}
        errors = validate_personality(spec)
        assert any("neuroticism" in e for e in errors)

    def test_invalid_empathy_style(self):
        spec = _minimal_spec()
        spec["emotional_profile"] = {"empathy_style": "aggressive"}
        errors = validate_personality(spec)
        assert any("empathy_style" in e for e in errors)

    def test_emotional_range_values(self):
        spec = _minimal_spec()
        spec["emotional_profile"] = {"emotional_range": {"joy": 2.0}}
        errors = validate_personality(spec)
        assert any("joy" in e for e in errors)

    def test_invalid_trigger_category(self):
        spec = _minimal_spec()
        spec["emotional_profile"] = {"triggers": {"angers": ["stuff"]}}
        errors = validate_personality(spec)
        assert any("angers" in e for e in errors)

    def test_vulnerability_missing_trait(self):
        spec = _minimal_spec()
        spec["vulnerabilities"] = [{"description": "no trait field"}]
        errors = validate_personality(spec)
        assert any("trait" in e for e in errors)

    def test_invalid_shadow_pattern(self):
        spec = _minimal_spec()
        spec["vulnerabilities"] = [{"trait": "x", "shadow_pattern": "rage"}]
        errors = validate_personality(spec)
        assert any("shadow_pattern" in e for e in errors)

    def test_invalid_verbosity(self):
        spec = _minimal_spec()
        spec["preferences"] = {"communication": {"verbosity": "extreme"}}
        errors = validate_personality(spec)
        assert any("verbosity" in e for e in errors)

    def test_invalid_risk_appetite(self):
        spec = _minimal_spec()
        spec["preferences"] = {"decision_making": {"risk_appetite": "reckless"}}
        errors = validate_personality(spec)
        assert any("risk_appetite" in e for e in errors)

    def test_anti_patterns_must_be_strings(self):
        spec = _minimal_spec()
        spec["anti_patterns"] = [123]
        errors = validate_personality(spec)
        assert any("anti_patterns" in e for e in errors)

    def test_override_hierarchy_element_must_be_string(self):
        """A non-str override_hierarchy element (e.g. a YAML 'task_completion: high'
        list item that parses into a dict) must be flagged at validation time so the
        SessionStart guardrails join doesn't crash with an opaque TypeError."""
        spec = _minimal_spec()
        spec["safety"] = {"override_hierarchy": ["safety", {"task_completion": "high"}]}
        errors = validate_personality(spec)
        assert any("override_hierarchy" in e for e in errors)

    def test_override_hierarchy_all_strings_valid(self):
        """A well-formed all-string override_hierarchy must still pass cleanly."""
        spec = _minimal_spec()
        spec["safety"] = {"override_hierarchy": ["safety", "user_wellbeing"]}
        errors = validate_personality(spec)
        assert errors == []

    def test_invalid_tone_shift(self):
        spec = _minimal_spec()
        spec["adaptive"] = {"when_angry": {"tone_shift": "aggressive"}}
        errors = validate_personality(spec)
        assert any("tone_shift" in e for e in errors)

    def test_invalid_default_mood(self):
        spec = _minimal_spec()
        spec["consciousness"] = {"default_mood": "berserker"}
        errors = validate_personality(spec)
        assert any("default_mood" in e for e in errors)

    def test_mood_volatility_range(self):
        spec = _minimal_spec()
        spec["consciousness"] = {"mood_volatility": 5.0}
        errors = validate_personality(spec)
        assert any("mood_volatility" in e for e in errors)

    def test_invalid_shadow_susceptibility_key(self):
        spec = _minimal_spec()
        spec["consciousness"] = {"shadow_susceptibility": {"rage": 0.5}}
        errors = validate_personality(spec)
        assert any("rage" in e for e in errors)

    def test_wrong_schema_version(self):
        spec = _minimal_spec()
        spec["schema"] = "spark-personality-chip.v99"
        errors = validate_personality(spec)
        assert any("schema" in e.lower() or "v99" in e for e in errors)

    def test_no_schema_field_is_ok(self):
        """Schema field is optional — absence is fine."""
        spec = _minimal_spec()
        del spec["schema"]
        errors = validate_personality(spec)
        assert errors == []

    def test_custom_fields_ignored(self):
        """Unknown top-level fields should not cause errors."""
        spec = _minimal_spec()
        spec["custom_section"] = {"anything": "goes"}
        errors = validate_personality(spec)
        assert errors == []


class TestBuild:
    """Tests for build_personality()."""

    def test_minimal_build(self):
        chip = build_personality(_minimal_spec())
        assert isinstance(chip, PersonalityChip)
        assert chip.id == "test-bot"
        assert chip.name == "TestBot"
        assert chip.archetype == "builder"  # default
        assert chip.openness == 0.50  # default

    def test_full_build(self):
        chip = build_personality(_full_spec())
        assert chip.id == "full-bot"
        assert chip.archetype == "oracle"
        assert chip.openness == 0.80
        assert chip.self_awareness == 0.85
        assert len(chip.vulnerabilities) == 1
        assert len(chip.strengths) == 1
        assert len(chip.anti_patterns) == 2
        assert chip.default_mood == "oracle"
        assert chip.carry_over_weight == 0.25

    def test_raw_preserved(self):
        spec = _full_spec()
        chip = build_personality(spec)
        assert chip._raw == spec

    def test_defaults_are_balanced(self):
        """Minimal spec should produce perfectly balanced traits."""
        chip = build_personality(_minimal_spec())
        assert chip.openness == 0.50
        assert chip.conscientiousness == 0.50
        assert chip.extraversion == 0.50
        assert chip.agreeableness == 0.50
        assert chip.neuroticism == 0.50
        assert chip.self_awareness == 0.50
        assert chip.empathy_style == "reflective"
