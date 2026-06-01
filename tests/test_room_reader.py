"""Tests for room_reader module."""

import json
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
