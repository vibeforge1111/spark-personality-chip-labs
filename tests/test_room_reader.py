"""Tests for room_reader module."""

import json
from contextlib import contextmanager
import tempfile
from pathlib import Path
from unittest.mock import patch

from personality_engine.room_reader import (
    RoomReading,
    read_room,
    read_room_from_hook_input,
    get_trajectory_summary,
    _compute_trajectory,
    _load_trajectory,
    _save_trajectory,
    _validated_score,
)


class TestReadRoom:
    """Test the core read_room function."""

    def test_empty_text(self):
        r = read_room("", persist_trajectory=False)
        assert r.primary_state is None
        assert r.confidence == 0.0

    def test_frustrated_keywords(self):
        r = read_room("this is broken and still failing, nothing works", persist_trajectory=False)
        assert r.primary_state == "frustrated"
        assert r.confidence >= 0.3

    def test_confused_keywords(self):
        r = read_room("I don't understand how does this work, I'm lost", persist_trajectory=False)
        assert r.primary_state == "confused"
        assert r.confidence >= 0.3

    def test_excited_keywords(self):
        r = read_room("this is amazing, it works! finally! awesome!", persist_trajectory=False)
        assert r.primary_state == "excited"
        assert r.confidence >= 0.3

    def test_vulnerable_keywords(self):
        r = read_room("sorry, dumb question, I should know this", persist_trajectory=False)
        assert r.primary_state == "vulnerable"
        assert r.confidence >= 0.3

    def test_defensive_keywords(self):
        r = read_room("i already tried that, that's not the issue, you're wrong", persist_trajectory=False)
        assert r.primary_state == "defensive"
        assert r.confidence >= 0.3

    def test_exhausted_keywords(self):
        r = read_room("been at this for hours, I give up, exhausted", persist_trajectory=False)
        assert r.primary_state == "exhausted"
        assert r.confidence >= 0.3

    def test_curious_keywords(self):
        r = read_room("how does this work? what if we tried something different? interesting", persist_trajectory=False)
        assert r.primary_state == "curious"
        assert r.confidence >= 0.3

    def test_expert_keywords(self):
        r = read_room("i know the root cause, just need to skip the explanation", persist_trajectory=False)
        assert r.primary_state == "expert"
        assert r.confidence >= 0.3

    def test_rushed_keywords(self):
        r = read_room("this is urgent, need it asap, ship it right now", persist_trajectory=False)
        assert r.primary_state == "rushed"
        assert r.confidence >= 0.3

    def test_neutral_text(self):
        r = read_room("please create a function that adds two numbers", persist_trajectory=False)
        assert r.primary_state is None or r.confidence < 0.2

    def test_all_states_populated(self):
        r = read_room("broken and still failing, I don't understand", persist_trajectory=False)
        assert len(r.all_states) >= 1
        assert r.signals_found >= 2

    def test_syntactic_exclamation(self):
        r = read_room("why won't this work!!! still broken!!", persist_trajectory=False)
        assert r.primary_state == "frustrated"
        # Syntactic layer should boost confidence
        assert r.confidence >= 0.3

    def test_discourse_markers(self):
        r = read_room("i already told you this doesn't work, for the nth time", persist_trajectory=False)
        assert r.primary_state == "frustrated"
        assert r.confidence >= 0.4

    def test_capitalized_imperative_matches_rushed_syntax(self):
        r = read_room("Fix the deployment", persist_trajectory=False)
        assert r.primary_state == "rushed"

    def test_technical_acronyms_are_not_excitement(self):
        r = read_room("API JSON LLM RAG", persist_trajectory=False)
        assert r.primary_state is None

    def test_nontechnical_all_caps_remains_excitement(self):
        r = read_room("AMAZING", persist_trajectory=False)
        assert r.primary_state == "excited"


class TestReadRoomFromHookInput:
    """Test hook input parsing."""

    def test_command_field(self):
        r = read_room_from_hook_input({"command": "this is broken and still failing"})
        assert r.primary_state == "frustrated"

    def test_description_field(self):
        r = read_room_from_hook_input({"description": "I don't understand this error"})
        assert r.primary_state == "confused"

    def test_empty_input(self):
        r = read_room_from_hook_input({})
        assert r.primary_state is None

    def test_combined_fields(self):
        r = read_room_from_hook_input({
            "command": "python test.py",
            "description": "still failing after trying everything",
        })
        assert r.primary_state == "frustrated"

    def test_directory_names_do_not_become_emotional_evidence(self):
        r = read_room_from_hook_input({"file_path": "/tmp/frustrated/broken/worker.py"})
        assert r.primary_state is None


class TestTrajectory:
    """Test emotional trajectory computation."""

    def test_stable(self):
        entries = [
            {"ts": 1, "state": "neutral", "score": 0.3},
            {"ts": 2, "state": "neutral", "score": 0.3},
            {"ts": 3, "state": "neutral", "score": 0.3},
        ]
        assert _compute_trajectory(entries, 0.3) == "stable"

    def test_rising(self):
        entries = [
            {"ts": 1, "state": "frustrated", "score": 0.2},
            {"ts": 2, "state": "frustrated", "score": 0.4},
            {"ts": 3, "state": "frustrated", "score": 0.6},
        ]
        assert _compute_trajectory(entries, 0.8) == "rising"

    def test_falling(self):
        entries = [
            {"ts": 1, "state": "frustrated", "score": 0.8},
            {"ts": 2, "state": "frustrated", "score": 0.6},
            {"ts": 3, "state": "frustrated", "score": 0.4},
        ]
        assert _compute_trajectory(entries, 0.2) == "falling"

    def test_volatile(self):
        entries = [
            {"ts": 1, "state": "frustrated", "score": 0.8},
            {"ts": 2, "state": "excited", "score": 0.2},
            {"ts": 3, "state": "frustrated", "score": 0.9},
        ]
        assert _compute_trajectory(entries, 0.1) == "volatile"

    def test_too_few_entries(self):
        assert _compute_trajectory([], 0.5) == "stable"
        assert _compute_trajectory([{"ts": 1, "score": 0.5}], 0.5) == "stable"

    def test_load_trajectory_ignores_non_object_state(self, tmp_path):
        trajectory_file = tmp_path / "room_trajectory.json"
        trajectory_file.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

        with patch("personality_engine.room_reader._TRAJECTORY_FILE", trajectory_file):
            assert _load_trajectory() == []

    def test_load_trajectory_filters_malformed_entries(self, tmp_path):
        trajectory_file = tmp_path / "room_trajectory.json"
        trajectory_file.write_text(
            json.dumps({
                "entries": [
                    "bad",
                    {"ts": "not-a-number", "score": 0.4},
                    {"ts": 9999999999, "state": "curious", "score": 0.4},
                ],
            }),
            encoding="utf-8",
        )

        with patch("personality_engine.room_reader._TRAJECTORY_FILE", trajectory_file):
            entries = _load_trajectory()

        assert entries == [{"ts": 9999999999, "state": "curious", "score": 0.4}]

    def test_save_trajectory_cleans_temp_file_after_replace_failure(self, tmp_path):
        trajectory_file = tmp_path / "room_trajectory.json"

        with patch("personality_engine.room_reader._TRAJECTORY_FILE", trajectory_file):
            with patch("personality_engine.storage.os.replace", side_effect=OSError("boom")):
                _save_trajectory([{"ts": 1, "state": "curious", "score": 0.5}])

        assert list(tmp_path.glob("*.tmp")) == []

    def test_persisted_read_wraps_load_modify_save_in_one_lock(self, tmp_path):
        events = []

        @contextmanager
        def recording_lock(path):
            events.append(("lock", path))
            yield
            events.append(("unlock", path))

        trajectory_file = tmp_path / "room_trajectory.json"
        with patch("personality_engine.room_reader._TRAJECTORY_FILE", trajectory_file):
            with patch("personality_engine.room_reader.exclusive_file_lock", recording_lock):
                with patch("personality_engine.room_reader._load_trajectory", side_effect=lambda personality_id: events.append(("load", personality_id)) or []):
                    with patch("personality_engine.room_reader._save_trajectory", side_effect=lambda rows, personality_id: events.append(("save", personality_id))):
                        read_room("this is broken and still failing", persist_trajectory=True)

        assert [event[0] for event in events] == ["lock", "load", "save", "unlock"]

    def test_personality_trajectories_are_isolated_without_filename_collisions(self, tmp_path):
        with patch("personality_engine.room_reader._TRAJECTORY_DIR", tmp_path):
            read_room("this is amazing and awesome", personality_id="first/personality")
            read_room("this is broken and still failing", personality_id="first_personality")

            first = _load_trajectory("first/personality")
            second = _load_trajectory("first_personality")

        assert first[0]["state"] == "excited"
        assert second[0]["state"] == "frustrated"
        assert len(list(tmp_path.glob("room_trajectory_*.json"))) == 2

    def test_malformed_scores_do_not_crash_or_create_false_volatility(self):
        entries = [
            {"ts": 1, "state": "curious", "score": "high"},
            {"ts": 2, "state": "curious", "score": None},
            {"ts": 3, "state": "curious", "score": 0.4},
        ]
        assert _compute_trajectory(entries, 0.5) == "stable"

    def test_score_validation_rejects_bool_and_nonfinite_values(self):
        assert _validated_score(True) is None
        assert _validated_score("0.5") is None
        assert _validated_score(float("nan")) is None
        assert _validated_score(float("inf")) is None
        assert _validated_score(-0.5) == 0.0
        assert _validated_score(1.5) == 1.0

    def test_summary_averages_only_valid_scores(self):
        entries = [
            {"ts": 1, "state": "curious", "score": "high"},
            {"ts": 2, "state": "curious", "score": True},
            {"ts": 3, "state": "curious", "score": 0.4},
            {"ts": 4, "state": "curious", "score": 0.6},
        ]
        with patch("personality_engine.room_reader._load_trajectory", return_value=entries):
            summary = get_trajectory_summary()

        assert summary["trajectory"] == "stable"
        assert summary["interaction_count"] == 4
        assert summary["avg_intensity"] == 0.5
