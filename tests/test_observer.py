"""Tests for personality drift observer."""

import json
import logging
import math

import pytest
from personality_engine.schema import build_personality, SCHEMA_VERSION
from personality_engine import observer
from personality_engine.observer import get_drift_history, observe_response


def _make_chip():
    return build_personality({
        "schema": SCHEMA_VERSION,
        "identity": {"id": "obs-test", "name": "ObsTest"},
        "preferences": {
            "communication": {
                "verbosity": "terse",
                "formality": "professional",
            },
        },
        "emotional_profile": {
            "emotional_range": {
                "frustration": 0.15,
                "humor": 0.10,
            },
        },
        "anti_patterns": [
            "Never dismisses user concerns",
            "Never pretends to know something it doesn't",
        ],
    })


class TestAntiPatternDetection:

    def test_clean_response(self):
        chip = _make_chip()
        report = observe_response(chip, "Here's how to fix the bug.")
        assert report["drift_score"] == 0.0
        assert report["signals"] == []

    def test_dismissive_response(self):
        chip = _make_chip()
        report = observe_response(chip, "That's not important, who cares about edge cases.")
        assert report["drift_score"] > 0.0
        assert any(s["type"] == "anti_pattern_violation" for s in report["signals"])

    def test_false_certainty(self):
        chip = _make_chip()
        report = observe_response(chip, "I guarantee this will work, trust me on this.")
        assert report["drift_score"] > 0.0

    @pytest.mark.parametrize("anti_patterns", [None, "dismiss", [123, "Never dismisses user concerns"]])
    def test_malformed_anti_patterns_do_not_disable_observer(self, anti_patterns):
        chip = _make_chip()
        chip.anti_patterns = anti_patterns
        report = observe_response(chip, "That's not important, who cares.")
        assert isinstance(report["drift_score"], float)


class TestVoiceConsistency:

    def test_terse_personality_long_response(self):
        chip = _make_chip()
        long_text = "word " * 350
        report = observe_response(chip, long_text)
        assert any(s["type"] == "voice_drift" for s in report["signals"])

    def test_professional_with_casual_markers(self):
        chip = _make_chip()
        report = observe_response(chip, "lol gonna wanna kinda fix this tbh")
        assert any(s["type"] == "voice_drift" for s in report["signals"])

    def test_matching_voice(self):
        chip = _make_chip()
        report = observe_response(chip, "Fix the null check on line 42.")
        assert report["drift_score"] == 0.0

    @pytest.mark.parametrize("communication", ["terse", ["terse"], 1])
    def test_malformed_communication_does_not_disable_observer(self, communication):
        chip = _make_chip()
        chip.communication = communication
        report = observe_response(chip, "word " * 350)
        assert not any(signal["type"] == "voice_drift" for signal in report["signals"])


class TestEmotionalRange:

    def test_high_frustration_low_range(self):
        chip = _make_chip()
        report = observe_response(chip, "This is frustrated and annoying, ugh.")
        assert any(s["type"] == "emotional_range_violation" for s in report["signals"])

    def test_within_range(self):
        chip = _make_chip()
        report = observe_response(chip, "This approach works well.")
        # No emotion markers = no violation
        emotional_violations = [
            s for s in report["signals"]
            if s["type"] == "emotional_range_violation"
        ]
        assert emotional_violations == []

    @pytest.mark.parametrize("configured", ["low", None, True, math.inf, math.nan])
    def test_malformed_emotional_range_value_is_ignored(self, configured):
        chip = _make_chip()
        chip.emotional_range = {"frustration": configured}
        report = observe_response(chip, "This is frustrated and annoying, ugh.")
        assert not any(signal["type"] == "emotional_range_violation" for signal in report["signals"])


class TestRecommendations:

    def test_high_drift_recommendation(self):
        chip = _make_chip()
        # Trigger multiple violations at once
        report = observe_response(
            chip,
            "That's not important lol gonna wanna kinda fix this tbh "
            "I guarantee trust me on this who cares"
        )
        assert report["drift_score"] > 0.3
        assert report["recommendation"] is not None

    def test_signal_count_bonus_is_bounded(self):
        chip = _make_chip()
        chip.anti_patterns = ["Never dismisses user concerns"] * 10
        report = observe_response(chip, "That's not important.")
        assert len(report["signals"]) == 10
        assert report["drift_score"] == 0.8


class TestDriftHistory:

    def test_reads_only_bounded_tail_and_returns_latest_valid_rows(self, tmp_path, monkeypatch):
        monkeypatch.setattr(observer, "INSIGHTS_DIR", tmp_path)
        log = tmp_path / "personality_obs-test.jsonl"
        oversized_prefix = b"x" * (observer._MAX_HISTORY_TAIL_BYTES + 64)
        rows = [{"index": index} for index in range(5)]
        log.write_bytes(oversized_prefix + b"\n" + b"\n".join(json.dumps(row).encode() for row in rows) + b"\n")

        assert get_drift_history("obs-test", limit=3) == rows[-3:]

    def test_skips_malformed_and_non_object_tail_rows(self, tmp_path, monkeypatch):
        monkeypatch.setattr(observer, "INSIGHTS_DIR", tmp_path)
        log = tmp_path / "personality_obs-test.jsonl"
        log.write_bytes(b'{"index": 1}\nnot-json\n[]\n\xff\n{"index": 2}\n')

        assert get_drift_history("obs-test", limit=10) == [{"index": 1}, {"index": 2}]

    def test_non_positive_limit_reads_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(observer, "INSIGHTS_DIR", tmp_path)
        (tmp_path / "personality_obs-test.jsonl").write_text('{"index": 1}\n', encoding="utf-8")

        assert get_drift_history("obs-test", limit=0) == []

    def test_persistence_failure_is_visible_without_path_reflection(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(observer, "INSIGHTS_DIR", tmp_path / "private-path")
        monkeypatch.setattr(observer.Path, "mkdir", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("/secret/path")))
        caplog.set_level(logging.WARNING, logger="personality_engine.observer")

        observer._log_drift("obs-test", {
            "drift_score": 0.5,
            "timestamp": "2026-07-21T00:00:00Z",
            "signals": [],
            "session_id": "session",
        })

        assert "drift observation persistence failed: OSError" in caplog.text
        assert "/secret/path" not in caplog.text
