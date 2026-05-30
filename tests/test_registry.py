"""Tests for personality registry state loading."""

import json

from personality_engine.registry import PersonalityRegistry
from personality_engine.schema import PersonalityChip


def test_registry_ignores_top_level_non_object_state(tmp_path):
    registry_file = tmp_path / "personality_registry.json"
    registry_file.write_text("[]", encoding="utf-8")

    registry = PersonalityRegistry(registry_file)

    assert registry.get_assignments() == {}
    assert registry.get_personality("agent") is None


def test_registry_sanitizes_malformed_active_state(tmp_path):
    registry_file = tmp_path / "personality_registry.json"
    registry_file.write_text(
        json.dumps({
            "active": {
                "agent-ok": "helper",
                "agent-bad": 42,
            },
            "default": ["not-a-personality-id"],
        }),
        encoding="utf-8",
    )

    registry = PersonalityRegistry(registry_file)

    assert registry.get_assignments() == {"agent-ok": "helper"}
    assert registry.get_personality("unknown") is None


def test_registry_keeps_valid_assignments(tmp_path):
    registry_file = tmp_path / "personality_registry.json"
    registry = PersonalityRegistry(registry_file)
    registry.install(PersonalityChip(id="helper", name="Helper"))
    registry.assign("agent-1", "helper")
    registry.set_default("helper")

    reloaded = PersonalityRegistry(registry_file)
    reloaded.install(PersonalityChip(id="helper", name="Helper"))

    assert reloaded.get_assignments() == {"agent-1": "helper"}
    assert reloaded.get_personality("agent-1").id == "helper"
    assert reloaded.get_personality("unknown").id == "helper"
