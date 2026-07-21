"""Tests for ib_connector module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from personality_engine.schema import PersonalityChip
from personality_engine.ib_connector import (
    build_builder_behavioral_rules,
    build_builder_persona_summary,
    build_builder_personality_import,
    map_chip_to_evolver_traits,
    sync_to_intelligence_builder,
    read_evolver_state,
    _validate_evolver_state_path,
)


def _make_chip(**overrides) -> PersonalityChip:
    defaults = {
        "id": "test-chip",
        "name": "Test Chip",
        "agreeableness": 0.70,
        "extraversion": 0.50,
        "conscientiousness": 0.65,
        "neuroticism": 0.30,
        "openness": 0.75,
        "social_awareness": 0.60,
        "empathy_style": "reflective",
        "communication": {"humor_frequency": "occasional"},
        "decision_making": {"risk_appetite": "moderate"},
    }
    defaults.update(overrides)
    return PersonalityChip(**defaults)


class TestMapChipToEvolverTraits:
    def test_returns_five_traits(self):
        traits = map_chip_to_evolver_traits(_make_chip())
        assert set(traits.keys()) == {"warmth", "directness", "playfulness", "pacing", "assertiveness"}

    def test_all_traits_in_range(self):
        traits = map_chip_to_evolver_traits(_make_chip())
        for name, val in traits.items():
            assert 0.0 <= val <= 1.0, f"{name} = {val} out of range"

    def test_high_agreeableness_high_warmth(self):
        high = map_chip_to_evolver_traits(_make_chip(agreeableness=0.95, social_awareness=0.90))
        low = map_chip_to_evolver_traits(_make_chip(agreeableness=0.15, social_awareness=0.20))
        assert high["warmth"] > low["warmth"]

    def test_nurturing_empathy_boosts_warmth(self):
        nurturing = map_chip_to_evolver_traits(_make_chip(empathy_style="nurturing"))
        challenging = map_chip_to_evolver_traits(_make_chip(empathy_style="challenging"))
        assert nurturing["warmth"] > challenging["warmth"]

    def test_high_openness_high_playfulness(self):
        high = map_chip_to_evolver_traits(_make_chip(openness=0.90))
        low = map_chip_to_evolver_traits(_make_chip(openness=0.15))
        assert high["playfulness"] > low["playfulness"]

    def test_humor_boosts_playfulness(self):
        frequent = map_chip_to_evolver_traits(_make_chip(communication={"humor_frequency": "frequent"}))
        never = map_chip_to_evolver_traits(_make_chip(communication={"humor_frequency": "never"}))
        assert frequent["playfulness"] > never["playfulness"]

    def test_low_neuroticism_high_assertiveness(self):
        calm = map_chip_to_evolver_traits(_make_chip(neuroticism=0.10))
        anxious = map_chip_to_evolver_traits(_make_chip(neuroticism=0.90))
        assert calm["assertiveness"] > anxious["assertiveness"]

    def test_bold_risk_boosts_assertiveness(self):
        bold = map_chip_to_evolver_traits(_make_chip(decision_making={"risk_appetite": "bold"}))
        conservative = map_chip_to_evolver_traits(_make_chip(decision_making={"risk_appetite": "conservative"}))
        assert bold["assertiveness"] > conservative["assertiveness"]


class TestSyncToIntelligenceBuilder:
    def test_writes_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "personality_evolution_v1.json"
            chip = _make_chip()
            state = sync_to_intelligence_builder(chip, state_path=path)

            assert path.exists()
            written = json.loads(path.read_text())
            assert written["version"] == 1
            assert "traits" in written
            assert written["last_signals"]["personality_id"] == "test-chip"

    def test_preserves_interaction_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "personality_evolution_v1.json"
            # Write existing state with interaction count
            path.write_text(json.dumps({"interaction_count": 42}))

            chip = _make_chip()
            state = sync_to_intelligence_builder(chip, state_path=path)
            assert state["interaction_count"] == 42

    def test_malformed_interaction_count_does_not_block_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "personality_evolution_v1.json"
            path.write_text(json.dumps({"interaction_count": "not-an-int"}))

            chip = _make_chip()
            state = sync_to_intelligence_builder(chip, state_path=path)
            assert state["interaction_count"] == 0
            assert state["last_signals"]["personality_id"] == "test-chip"

    def test_non_object_existing_state_does_not_block_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "personality_evolution_v1.json"
            path.write_text(json.dumps(["unexpected", "state"]))

            chip = _make_chip()
            state = sync_to_intelligence_builder(chip, state_path=path)
            assert state["interaction_count"] == 0
            assert state["last_signals"]["personality_id"] == "test-chip"

    def test_fresh_file_zero_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "personality_evolution_v1.json"
            chip = _make_chip()
            state = sync_to_intelligence_builder(chip, state_path=path)
            assert state["interaction_count"] == 0

    def test_directory_creation_failure_does_not_crash_sync(self, tmp_path):
        path = tmp_path / "unavailable" / "personality_evolution_v1.json"
        with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
            state = sync_to_intelligence_builder(_make_chip(), state_path=path)
        assert state["interaction_count"] == 0
        assert state["last_signals"]["personality_id"] == "test-chip"
        assert not path.exists()


class TestBuildBuilderPersonalityImport:
    def test_builds_builder_facing_persona_summary(self):
        chip = _make_chip(
            name="Artemis",
            archetype="oracle",
            voice_signature="precise, warm, unhurried",
            tagline="I see the pattern before the problem.",
        )
        summary = build_builder_persona_summary(chip)
        assert summary == "precise, warm, unhurried. I see the pattern before the problem"

    def test_derives_behavioral_rules_from_chip_preferences(self):
        chip = _make_chip(
            voice_signature="direct, energetic, action-biased",
            communication={
                "verbosity": "terse",
                "formality": "casual",
                "explanation_style": "stepwise",
                "humor_frequency": "never",
            },
            decision_making={"risk_appetite": "bold"},
            anti_patterns=["Never blocks progress for theoretical concerns"],
        )
        rules = build_builder_behavioral_rules(chip)
        assert "Sound direct, energetic, action-biased." in rules
        assert "Keep replies tight and skip filler." in rules
        assert "Keep the register casual." in rules
        assert "When explanation is needed, prefer a stepwise explanation style." in rules
        assert "Do not force humor or banter." in rules
        assert "Make decisive recommendations when the path is clear." in rules
        assert "Never blocks progress for theoretical concerns." in rules

    def test_builds_import_payload_matching_builder_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".spark"
            path = root / "personality_evolution_v1.json"
            chip = _make_chip(
                id="forge",
                name="Forge",
                voice_signature="direct, energetic, action-biased",
                tagline="Ship it, learn, ship again.",
            )
            with patch("personality_engine.ib_connector.IB_STATE_ROOT", root):
                payload = build_builder_personality_import(
                    chip,
                    human_id="human:telegram:111",
                    agent_id="agent:human:telegram:111",
                    evolver_state_path=path,
                )

            assert payload["human_id"] == "human:telegram:111"
            assert payload["agent_id"] == "agent:human:telegram:111"
            assert payload["persona_name"] == "Forge"
            assert payload["personality_id"] == "forge"
            assert payload["base_traits"] == payload["evolver_state"]["traits"]
            assert payload["behavioral_rules"]
            assert path.exists()

    def test_rejects_hook_selected_path_outside_spark_state(self, tmp_path):
        root = tmp_path / ".spark"
        with patch("personality_engine.ib_connector.IB_STATE_ROOT", root):
            with pytest.raises(ValueError, match="outside the allowed Spark state"):
                build_builder_personality_import(
                    _make_chip(), human_id="human", agent_id="agent",
                    evolver_state_path=tmp_path / "outside.json",
                )


class TestValidateEvolverStatePath:
    def test_accepts_descendant_of_spark_state_root(self, tmp_path):
        root = tmp_path / ".spark"
        with patch("personality_engine.ib_connector.IB_STATE_ROOT", root):
            assert _validate_evolver_state_path(root / "nested" / "state.json") == (
                root / "nested" / "state.json"
            ).resolve()

    def test_rejects_prefix_sibling_and_traversal(self, tmp_path):
        root = tmp_path / ".spark"
        with patch("personality_engine.ib_connector.IB_STATE_ROOT", root):
            for candidate in (
                tmp_path / ".spark-evil" / "state.json",
                root / ".." / "outside.json",
            ):
                with pytest.raises(ValueError, match="outside the allowed Spark state"):
                    _validate_evolver_state_path(candidate)

    def test_rejects_symlink_escape(self, tmp_path):
        root = tmp_path / ".spark"
        outside = tmp_path / "outside"
        root.mkdir()
        outside.mkdir()
        (root / "escape").symlink_to(outside, target_is_directory=True)
        with patch("personality_engine.ib_connector.IB_STATE_ROOT", root):
            with pytest.raises(ValueError, match="outside the allowed Spark state"):
                _validate_evolver_state_path(root / "escape" / "state.json")

    def test_rejects_root_directory_itself(self, tmp_path):
        root = tmp_path / ".spark"
        with patch("personality_engine.ib_connector.IB_STATE_ROOT", root):
            with pytest.raises(ValueError, match="must name a file"):
                _validate_evolver_state_path(root)


class TestReadEvolverState:
    def test_returns_none_when_missing(self):
        assert read_evolver_state(Path("/nonexistent/path.json")) is None

    def test_reads_written_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({"version": 1, "traits": {"warmth": 0.6}}))
            state = read_evolver_state(path)
            assert state["traits"]["warmth"] == 0.6
