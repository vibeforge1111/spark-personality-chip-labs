"""Tests for nl_traits module — NL personality preference extraction."""

import pytest

from personality_engine.nl_traits import (
    extract_trait_deltas,
    has_personality_preference,
    describe_deltas,
)


# ── Directness patterns ──


class TestDirectnessPatterns:
    def test_be_more_direct(self):
        deltas = extract_trait_deltas("be more direct")
        assert deltas["directness"] > 0

    def test_too_direct(self):
        deltas = extract_trait_deltas("you're too direct")
        assert "directness" in deltas

    def test_be_concise(self):
        deltas = extract_trait_deltas("be more concise please")
        assert deltas["directness"] > 0
        assert deltas["pacing"] > 0

    def test_skip_preamble(self):
        deltas = extract_trait_deltas("skip the preamble")
        assert deltas["directness"] > 0
        assert deltas["pacing"] > 0

    def test_skip_explanation(self):
        deltas = extract_trait_deltas("skip the explanation, just give me code")
        assert deltas["directness"] > 0

    def test_over_explain(self):
        deltas = extract_trait_deltas("you over-explain things")
        assert deltas["directness"] > 0

    def test_too_explain(self):
        deltas = extract_trait_deltas("you too explain everything")
        assert deltas["directness"] > 0

    def test_get_to_the_point(self):
        deltas = extract_trait_deltas("just get to the point")
        assert deltas["directness"] > 0
        assert deltas["pacing"] > 0

    def test_less_verbose(self):
        deltas = extract_trait_deltas("be less verbose")
        assert deltas["directness"] > 0

    def test_more_detail(self):
        deltas = extract_trait_deltas("give me more detail")
        assert deltas["directness"] < 0
        assert deltas["pacing"] < 0

    def test_more_thorough(self):
        deltas = extract_trait_deltas("be more thorough")
        assert deltas["directness"] < 0


# ── Warmth patterns ──


class TestWarmthPatterns:
    def test_be_warmer(self):
        deltas = extract_trait_deltas("be warmer")
        assert deltas["warmth"] > 0

    def test_more_warm(self):
        deltas = extract_trait_deltas("be more warm")
        assert deltas["warmth"] > 0

    def test_too_formal(self):
        deltas = extract_trait_deltas("you're too formal")
        assert deltas["warmth"] > 0
        assert deltas["playfulness"] > 0

    def test_less_formal(self):
        deltas = extract_trait_deltas("be less formal")
        assert deltas["warmth"] > 0

    def test_loosen_up(self):
        deltas = extract_trait_deltas("loosen up a bit")
        assert deltas["warmth"] > 0
        assert deltas["playfulness"] > 0

    def test_more_friendly(self):
        deltas = extract_trait_deltas("be more friendly")
        assert deltas["warmth"] > 0

    def test_too_cold(self):
        deltas = extract_trait_deltas("that's too cold")
        assert deltas["warmth"] > 0

    def test_more_professional(self):
        deltas = extract_trait_deltas("be more professional")
        assert deltas["warmth"] < 0
        assert deltas["playfulness"] < 0


# ── Playfulness patterns ──


class TestPlayfulnessPatterns:
    def test_be_playful(self):
        deltas = extract_trait_deltas("be more playful")
        assert deltas["playfulness"] > 0

    def test_more_energy(self):
        deltas = extract_trait_deltas("I want more energy")
        assert deltas["playfulness"] > 0

    def test_more_enthusiasm(self):
        deltas = extract_trait_deltas("show more enthusiasm")
        assert deltas["playfulness"] > 0

    def test_tone_it_down(self):
        deltas = extract_trait_deltas("tone it down")
        assert deltas["playfulness"] < 0
        assert deltas["assertiveness"] < 0

    def test_dial_it_back(self):
        deltas = extract_trait_deltas("dial it back a bit")
        assert deltas["playfulness"] < 0

    def test_more_fun(self):
        deltas = extract_trait_deltas("have more fun with it")
        assert deltas["playfulness"] > 0

    def test_too_serious(self):
        deltas = extract_trait_deltas("you're too serious")
        assert deltas["playfulness"] > 0

    def test_be_serious(self):
        deltas = extract_trait_deltas("be more serious")
        assert deltas["playfulness"] < 0


# ── Pacing patterns ──


class TestPacingPatterns:
    def test_slow_down(self):
        deltas = extract_trait_deltas("slow down please")
        assert deltas["pacing"] < 0
        assert deltas["directness"] < 0

    def test_slower_down(self):
        deltas = extract_trait_deltas("go slower down")
        assert deltas["pacing"] < 0

    def test_explain_more(self):
        deltas = extract_trait_deltas("explain more about this")
        assert deltas["pacing"] < 0

    def test_speed_up(self):
        deltas = extract_trait_deltas("speed up")
        assert deltas["pacing"] > 0

    def test_speed_it_up(self):
        deltas = extract_trait_deltas("speed it up please")
        assert deltas["pacing"] > 0

    def test_take_your_time(self):
        deltas = extract_trait_deltas("take your time with this")
        assert deltas["pacing"] < 0


# ── Assertiveness patterns ──


class TestAssertivenessPatterns:
    def test_stop_hedging(self):
        deltas = extract_trait_deltas("stop hedging")
        assert deltas["assertiveness"] > 0
        assert deltas["directness"] > 0

    def test_more_assertive(self):
        deltas = extract_trait_deltas("be more assertive")
        assert deltas["assertiveness"] > 0

    def test_less_assertive(self):
        deltas = extract_trait_deltas("be less assertive")
        assert deltas["assertiveness"] < 0
        assert deltas["warmth"] > 0

    def test_more_gentle(self):
        deltas = extract_trait_deltas("be more gentle")
        assert deltas["assertiveness"] < 0

    def test_be_confident(self):
        deltas = extract_trait_deltas("be more confident")
        assert deltas["assertiveness"] > 0

    def test_stop_apologizing(self):
        deltas = extract_trait_deltas("stop apologizing")
        assert deltas["assertiveness"] > 0
        assert deltas["directness"] > 0

    def test_stop_saying_sorry(self):
        deltas = extract_trait_deltas("stop saying sorry all the time")
        assert deltas["assertiveness"] > 0

    def test_calm_down(self):
        deltas = extract_trait_deltas("calm down")
        assert deltas["assertiveness"] < 0

    def test_calm_description_is_not_mistaken_for_style_intent(self):
        assert extract_trait_deltas("the lake is calm today") == {}

    def test_explicit_relax_request_is_style_intent(self):
        deltas = extract_trait_deltas("can you relax")

        assert deltas["assertiveness"] < 0
        assert deltas["warmth"] > 0

    def test_just_tell_me(self):
        deltas = extract_trait_deltas("just tell me the answer")
        assert deltas["directness"] > 0
        assert deltas["assertiveness"] > 0


# ── Edge cases ──


class TestEdgeCases:
    def test_empty_string(self):
        assert extract_trait_deltas("") == {}

    def test_none_like_empty(self):
        assert extract_trait_deltas("   ") == {}

    def test_neutral_text(self):
        assert extract_trait_deltas("how do I install numpy?") == {}

    def test_neutral_code_question(self):
        assert extract_trait_deltas("what does this function do?") == {}

    def test_case_insensitive(self):
        lower = extract_trait_deltas("be more direct")
        upper = extract_trait_deltas("BE MORE DIRECT")
        assert lower == upper

    def test_multiple_patterns_merge(self):
        """When multiple patterns match, deltas should merge additively."""
        deltas = extract_trait_deltas("be more direct and stop hedging please")
        # directness from "be more direct" (0.4) + "stop hedging" (0.3) = 0.7
        assert deltas["directness"] > 0.5
        assert deltas["assertiveness"] > 0

    def test_opposing_signals(self):
        """Contradictory patterns should partially cancel."""
        deltas = extract_trait_deltas("be more direct but also explain more")
        # directness: +0.4 from direct, -0.2 from explain more = +0.2
        assert "directness" in deltas

    def test_deltas_clamped(self):
        """Even with many merging patterns, deltas stay in [-1, 1]."""
        # Stack many directness patterns
        text = "be more direct, be concise, skip the preamble, get to the point, less verbose"
        deltas = extract_trait_deltas(text)
        for val in deltas.values():
            assert -1.0 <= val <= 1.0


# ── Utility functions ──


class TestHasPersonalityPreference:
    def test_positive(self):
        assert has_personality_preference("be more direct") is True

    def test_negative(self):
        assert has_personality_preference("what is python?") is False

    def test_empty(self):
        assert has_personality_preference("") is False

    def test_whitespace(self):
        assert has_personality_preference("   ") is False


class TestDescribeDeltas:
    def test_empty(self):
        assert describe_deltas({}) == "no changes"

    def test_single_positive(self):
        result = describe_deltas({"directness": 0.4})
        assert "directness +0.4" in result

    def test_single_negative(self):
        result = describe_deltas({"pacing": -0.3})
        assert "pacing -0.3" in result

    def test_multiple_sorted(self):
        result = describe_deltas({"warmth": 0.3, "directness": 0.4})
        # Should be alphabetically sorted
        assert result.index("directness") < result.index("warmth")
