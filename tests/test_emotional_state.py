"""Tests for emotional_state module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from personality_engine.schema import PersonalityChip
from personality_engine.emotional_state import (
    PADVector,
    get_baseline_pad,
    appraise,
    update_emotional_state,
    pad_to_primary_emotion,
    pad_to_mood,
    pad_to_intensity,
    build_emotional_state_for_bridge,
    reset_emotional_state,
    _load_state,
    _save_state,
)


def _make_chip(**overrides) -> PersonalityChip:
    """Create a test chip with sensible defaults."""
    defaults = {
        "id": "test-chip",
        "name": "Test Chip",
        "agreeableness": 0.70,
        "extraversion": 0.50,
        "conscientiousness": 0.65,
        "neuroticism": 0.30,
        "openness": 0.75,
        "social_awareness": 0.60,
        "carry_over_weight": 0.25,
        "default_mood": "builder",
    }
    defaults.update(overrides)
    return PersonalityChip(**defaults)


class TestPADVector:
    def test_to_dict(self):
        pad = PADVector(0.5, -0.3, 0.1)
        d = pad.to_dict()
        assert d["pleasure"] == 0.5
        assert d["arousal"] == -0.3
        assert d["dominance"] == 0.1

    def test_from_dict(self):
        pad = PADVector.from_dict({"pleasure": 0.2, "arousal": -0.1, "dominance": 0.8})
        assert pad.pleasure == 0.2
        assert pad.arousal == -0.1
        assert pad.dominance == 0.8

    def test_clamp(self):
        pad = PADVector(1.5, -1.5, 0.0).clamp()
        assert pad.pleasure == 1.0
        assert pad.arousal == -1.0
        assert pad.dominance == 0.0


class TestBaselinePAD:
    def test_high_agreeableness_positive_pleasure(self):
        chip = _make_chip(agreeableness=0.90, neuroticism=0.10)
        pad = get_baseline_pad(chip)
        assert pad.pleasure > 0.0

    def test_high_extraversion_positive_arousal(self):
        chip = _make_chip(extraversion=0.90, openness=0.80)
        pad = get_baseline_pad(chip)
        assert pad.arousal > 0.0

    def test_balanced_chip_near_zero(self):
        chip = _make_chip(
            agreeableness=0.50, extraversion=0.50,
            conscientiousness=0.50, neuroticism=0.50, openness=0.50,
        )
        pad = get_baseline_pad(chip)
        assert abs(pad.pleasure) < 0.15
        assert abs(pad.arousal) < 0.15
        assert abs(pad.dominance) < 0.15


class TestAppraise:
    def test_frustrated_shifts_pleasure_down(self):
        delta = appraise("frustrated")
        assert delta.pleasure < 0

    def test_excited_shifts_pleasure_up(self):
        delta = appraise("excited")
        assert delta.pleasure > 0

    def test_exhausted_lowers_arousal(self):
        delta = appraise("exhausted")
        assert delta.arousal < 0

    def test_unknown_state_zero_delta(self):
        delta = appraise("nonexistent_state")
        assert delta.pleasure == 0 and delta.arousal == 0 and delta.dominance == 0

    def test_none_state_zero_delta(self):
        delta = appraise(None)
        assert delta.pleasure == 0

    def test_intensity_scales(self):
        full = appraise("frustrated", intensity=1.0)
        half = appraise("frustrated", intensity=0.5)
        assert abs(half.pleasure) < abs(full.pleasure)


class TestUpdateEmotionalState:
    def test_returns_pad_vector(self):
        chip = _make_chip()
        pad = update_emotional_state(chip, user_state="curious", persist=False)
        assert isinstance(pad, PADVector)

    def test_frustrated_lowers_pleasure(self):
        chip = _make_chip()
        baseline = get_baseline_pad(chip)
        pad = update_emotional_state(chip, user_state="frustrated", persist=False)
        assert pad.pleasure < baseline.pleasure + 0.1  # Should be lower or roughly same

    def test_none_state_decays_toward_baseline(self):
        chip = _make_chip()
        pad = update_emotional_state(chip, user_state=None, persist=False)
        assert isinstance(pad, PADVector)


class TestPADMappings:
    def test_pad_to_emotion_steady(self):
        emotion = pad_to_primary_emotion(PADVector(0.0, 0.0, 0.0))
        assert isinstance(emotion, str)
        assert len(emotion) > 0

    def test_pad_to_emotion_positive(self):
        emotion = pad_to_primary_emotion(PADVector(0.5, 0.3, 0.1))
        assert emotion in ("delighted", "energized", "focused", "contemplative", "steady", "concerned", "gentle")

    def test_pad_to_mood(self):
        assert pad_to_mood(PADVector(0.0, 0.3, 0.3)) == "builder"
        assert pad_to_mood(PADVector(0.3, -0.3, 0.0)) == "zen"

    def test_pad_to_intensity_range(self):
        val = pad_to_intensity(PADVector(0.5, 0.5, 0.5))
        assert 0.1 <= val <= 0.9

    def test_pad_to_intensity_low_for_zero(self):
        val = pad_to_intensity(PADVector(0.0, 0.0, 0.0))
        assert val == 0.5  # Neutral


class TestBridgeIntegration:
    def test_build_emotional_state_for_bridge(self):
        chip = _make_chip()
        state = build_emotional_state_for_bridge(chip, user_state="curious", persist=False)

        assert "mood" in state
        assert "intensity" in state
        assert "primary_emotion" in state
        assert "confidence" in state
        assert "staleness_seconds" in state
        assert "pad_vector" in state
        assert state["mood"] in ("builder", "oracle", "zen", "chaos")
        assert 0.1 <= state["intensity"] <= 0.9

    def test_bridge_state_without_user_state(self):
        chip = _make_chip()
        state = build_emotional_state_for_bridge(chip, persist=False)
        assert isinstance(state["primary_emotion"], str)


class TestSaveStateCleanup:
    def test_load_state_ignores_non_object_state(self, tmp_path):
        state_file = tmp_path / "emotional_state.json"
        state_file.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

        with patch("personality_engine.emotional_state._STATE_FILE", state_file):
            pad, updated_at = _load_state()

        assert pad == PADVector()
        assert updated_at == 0.0

    def test_load_state_ignores_malformed_pad_or_timestamp(self, tmp_path):
        state_file = tmp_path / "emotional_state.json"
        state_file.write_text(
            json.dumps({"pad": ["not", "a", "mapping"], "updated_at": "bad"}),
            encoding="utf-8",
        )

        with patch("personality_engine.emotional_state._STATE_FILE", state_file):
            pad, updated_at = _load_state()

        assert pad == PADVector()
        assert updated_at == 0.0

    def test_save_state_cleans_temp_file_after_replace_failure(self, tmp_path):
        state_file = tmp_path / "emotional_state.json"

        with patch("personality_engine.emotional_state._STATE_FILE", state_file):
            with patch("os.replace", side_effect=OSError("simulated replace failure")):
                _save_state(PADVector(0.5, 0.3, 0.1))

        assert list(tmp_path.glob("*.tmp")) == []

    def test_save_state_normal_flow(self, tmp_path):
        state_file = tmp_path / "emotional_state.json"

        with patch("personality_engine.emotional_state._STATE_FILE", state_file):
            _save_state(PADVector(0.5, 0.3, 0.1))
            loaded_pad, updated_at = _load_state()

        assert abs(loaded_pad.pleasure - 0.5) < 0.01
        assert abs(loaded_pad.arousal - 0.3) < 0.01
        assert abs(loaded_pad.dominance - 0.1) < 0.01
        assert updated_at > 0
