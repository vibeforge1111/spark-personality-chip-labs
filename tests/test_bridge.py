"""Tests for consciousness bridge (bridge.v1 contract)."""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from personality_engine.schema import build_personality, SCHEMA_VERSION
from personality_engine.bridge import (
    build_bridge_payload,
    write_bridge,
    read_bridge,
    clear_bridge,
    refresh_bridge_emotional_state,
)


def _make_chip():
    return build_personality({
        "schema": SCHEMA_VERSION,
        "identity": {
            "id": "bridge-test",
            "name": "BridgeTest",
            "archetype": "oracle",
        },
        "traits": {
            "openness": 0.80,
            "extraversion": 0.40,
            "neuroticism": 0.25,
            "agreeableness": 0.65,
            "conscientiousness": 0.70,
        },
        "emotional_profile": {
            "self_awareness": 0.85,
            "self_regulation": 0.70,
            "social_awareness": 0.60,
            "empathy_style": "reflective",
            "emotional_range": {"curiosity": 0.90},
            "triggers": {"energizes": ["patterns"]},
        },
        "preferences": {
            "communication": {
                "verbosity": "moderate",
                "formality": "professional",
            },
        },
        "consciousness": {
            "default_mood": "oracle",
            "mood_volatility": 0.25,
            "shadow_susceptibility": {"overconfidence": 0.20},
            "carry_over_weight": 0.30,
            "reframe_preference": "redirect",
        },
        "safety": {
            "harm_avoidance": ["No manipulation"],
            "risk_level": "low",
        },
    })


class TestBridgeV1Schema:
    """Tests that the payload matches bridge.v1 contract exactly."""

    def test_schema_version(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["schema_version"] == "bridge.v1"

    def test_source(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["source"] == "spark-personality"

    def test_generated_at(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert "generated_at" in payload
        assert "T" in payload["generated_at"]  # ISO format

    def test_session(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip, session_id="test-session")
        assert payload["session"]["id"] == "test-session"
        assert payload["session"]["scope"] == "runtime"

    def test_meta(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["meta"]["ttl_seconds"] == 120
        assert payload["meta"]["personality_id"] == "bridge-test"
        assert payload["meta"]["personality_name"] == "BridgeTest"


class TestEmotionalState:

    def test_mood(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        state = payload["emotional_state"]
        assert state["mood"] == "oracle"

    def test_intensity_in_range(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert 0.0 < payload["emotional_state"]["intensity"] < 1.0

    def test_continuity_influence(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["emotional_state"]["continuity_influence"] == 0.30

    def test_primary_emotion(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["emotional_state"]["primary_emotion"] == "contemplative"

    def test_confidence(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["emotional_state"]["confidence"] == 0.85

    def test_staleness_seconds(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["emotional_state"]["staleness_seconds"] == 0

    def test_explicit_dynamic_state_is_published_unchanged(self):
        chip = _make_chip()
        dynamic = {
            "mood": "builder", "intensity": 0.72, "continuity_influence": 0.3,
            "primary_emotion": "focused", "confidence": 0.85,
            "staleness_seconds": 0, "pad_vector": {"pleasure": 0.1, "arousal": 0.2, "dominance": 0.3},
        }
        payload = build_bridge_payload(chip, emotional_state=dynamic)
        assert payload["emotional_state"] == dynamic


class TestGuidance:

    def test_response_pace(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["response_pace"] in (
            "slow", "measured", "balanced", "lively"
        )

    def test_verbosity_mapping(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        # moderate -> medium
        assert payload["guidance"]["verbosity"] == "medium"

    def test_tone_shape_valid(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["tone_shape"] in (
            "reassuring_and_clear", "calm_focus", "encouraging", "grounded_warm"
        )

    def test_ask_clarifying_question(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["ask_clarifying_question"] is False


class TestMission:

    def test_mission_anchor(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        assert "BridgeTest" in payload["mission"]["anchor"]
        assert "oracle" in payload["mission"]["anchor"]

    def test_mission_kernel(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        kernel = payload["mission"]["kernel"]
        assert kernel["non_harm"] is True
        assert kernel["service"] is True
        assert kernel["clarity"] is True


class TestBoundaries:

    def test_boundaries_structure(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        b = payload["boundaries"]
        assert b["user_guided"] is True
        assert b["no_autonomous_objectives"] is True
        assert b["no_manipulative_affect"] is True
        assert isinstance(b["max_influence"], (int, float))
        assert 0.0 < b["max_influence"] <= 1.0


class TestPersonalityExt:

    def test_shadow_config(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        shadow = payload["personality_ext"]["shadow_config"]
        assert shadow["susceptibility"]["overconfidence"] == 0.20
        assert shadow["reframe_preference"] == "redirect"

    def test_emotions_config(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        emotions = payload["personality_ext"]["emotions_config"]
        assert emotions["carry_over_weight"] == 0.30
        assert emotions["emotional_range"]["curiosity"] == 0.90
        assert emotions["baseline_mood"] == "oracle"
        assert emotions["mood_volatility"] == 0.25

    def test_safety_ext(self):
        chip = _make_chip()
        payload = build_bridge_payload(chip)
        safety = payload["personality_ext"]["safety"]
        assert "No manipulation" in safety["harm_avoidance"]
        assert safety["risk_level"] == "low"


class TestBridgeIO:

    def test_write_and_read(self, tmp_path):
        chip = _make_chip()
        bridge_path = tmp_path / "test_bridge.json"
        write_bridge(chip, bridge_path=bridge_path)

        payload = read_bridge(bridge_path)
        assert payload is not None
        assert payload["schema_version"] == "bridge.v1"
        assert payload["meta"]["personality_id"] == "bridge-test"

    def test_clear(self, tmp_path):
        chip = _make_chip()
        bridge_path = tmp_path / "test_bridge.json"
        write_bridge(chip, bridge_path=bridge_path)
        assert bridge_path.exists()

        clear_bridge(bridge_path)
        assert not bridge_path.exists()

    def test_clear_missing_file_is_noop(self, tmp_path):
        bridge_path = tmp_path / "missing_bridge.json"

        clear_bridge(bridge_path)

        assert not bridge_path.exists()

    def test_read_nonexistent(self, tmp_path):
        payload = read_bridge(tmp_path / "nope.json")
        assert payload is None

    def test_non_string_generated_at_is_ignored(self, tmp_path):
        bridge_path = tmp_path / "test_bridge.json"
        bridge_path.write_text(
            json.dumps({
                "schema_version": "bridge.v1",
                "generated_at": 123,
                "meta": {"ttl_seconds": 1},
            }),
            encoding="utf-8",
        )

        payload = read_bridge(bridge_path)

        assert payload is not None
        assert "_stale" not in payload

    def test_z_suffixed_generated_at_is_checked_for_staleness(self, tmp_path):
        bridge_path = tmp_path / "test_bridge.json"
        bridge_path.write_text(
            json.dumps({
                "schema_version": "bridge.v1",
                "generated_at": "2000-01-01T00:00:00Z",
                "meta": {"ttl_seconds": 1},
            }),
            encoding="utf-8",
        )

        payload = read_bridge(bridge_path)

        assert payload is not None
        assert payload["_stale"] is True

    def test_naive_generated_at_is_checked_for_staleness(self, tmp_path):
        """Older bridge files without timezone info should still honor TTL."""
        bridge_path = tmp_path / "test_bridge.json"
        bridge_path.write_text(
            json.dumps({
                "schema_version": "bridge.v1",
                "generated_at": "2000-01-01T00:00:00",
                "meta": {"ttl_seconds": 1},
            }),
            encoding="utf-8",
        )

        payload = read_bridge(bridge_path)

        assert payload is not None
        assert payload["_stale"] is True

    def test_fresh_naive_generated_at_is_not_marked_stale(self, tmp_path):
        bridge_path = tmp_path / "test_bridge.json"
        bridge_path.write_text(
            json.dumps({
                "schema_version": "bridge.v1",
                "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "meta": {"ttl_seconds": 120},
            }),
            encoding="utf-8",
        )

        payload = read_bridge(bridge_path)

        assert payload is not None
        assert "_stale" not in payload

    def test_read_non_object_bridge_returns_none(self, tmp_path):
        bridge_path = tmp_path / "test_bridge.json"
        bridge_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

        assert read_bridge(bridge_path) is None

    @pytest.mark.parametrize("ttl", ["120s", None, True, float("nan"), float("inf"), -1])
    def test_invalid_ttl_uses_bounded_default_and_still_surfaces_staleness(self, tmp_path, ttl):
        bridge_path = tmp_path / "test_bridge.json"
        bridge_path.write_text(json.dumps({
            "schema_version": "bridge.v1",
            "generated_at": "2000-01-01T00:00:00Z",
            "meta": {"ttl_seconds": ttl},
        }), encoding="utf-8")
        payload = read_bridge(bridge_path)
        assert payload is not None
        assert payload["_stale"] is True

    def test_refresh_publishes_the_same_dynamic_state(self, tmp_path):
        chip = _make_chip()
        bridge_path = tmp_path / "test_bridge.json"
        dynamic = {"mood": "zen", "intensity": 0.61, "primary_emotion": "steady"}
        with patch("personality_engine.emotional_state.build_emotional_state_for_bridge", return_value=dynamic) as build:
            payload = refresh_bridge_emotional_state(
                chip, user_state="curious", intensity=0.7,
                session_id="session-proof", bridge_path=bridge_path,
            )
        build.assert_called_once_with(chip, user_state="curious", intensity=0.7, persist=True)
        assert payload["emotional_state"] == dynamic
        assert read_bridge(bridge_path)["emotional_state"] == dynamic

    def test_write_bridge_preserves_old_file_after_replace_failure(self, tmp_path):
        chip = _make_chip()
        bridge_path = tmp_path / "test_bridge.json"
        old_payload = {"schema_version": "bridge.v1", "generated_at": "old"}
        bridge_path.write_text(json.dumps(old_payload), encoding="utf-8")

        with patch("personality_engine.storage.os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError):
                write_bridge(chip, bridge_path=bridge_path)

        assert json.loads(bridge_path.read_text(encoding="utf-8")) == old_payload
        assert list(tmp_path.glob("*.tmp")) == []


class TestVerbosityMapping:
    """Test all verbosity enum mappings."""

    def test_terse_to_concise(self):
        chip = build_personality({
            "identity": {"id": "verb-test", "name": "VerbTest"},
            "preferences": {"communication": {"verbosity": "terse"}},
        })
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["verbosity"] == "concise"

    def test_moderate_to_medium(self):
        chip = build_personality({
            "identity": {"id": "verb-test", "name": "VerbTest"},
            "preferences": {"communication": {"verbosity": "moderate"}},
        })
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["verbosity"] == "medium"

    def test_detailed_to_structured(self):
        chip = build_personality({
            "identity": {"id": "verb-test", "name": "VerbTest"},
            "preferences": {"communication": {"verbosity": "detailed"}},
        })
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["verbosity"] == "structured"

    def test_default_to_medium(self):
        chip = build_personality({
            "identity": {"id": "verb-test", "name": "VerbTest"},
        })
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["verbosity"] == "medium"

    def test_non_mapping_communication_falls_back_to_medium(self):
        chip = _make_chip()
        chip.communication = "detailed"
        payload = build_bridge_payload(chip)
        assert payload["guidance"]["verbosity"] == "medium"
        assert payload["guidance"]["verbosity"] == "medium"
