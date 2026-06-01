"""Tests for personality registry state persistence."""

import json
from unittest.mock import patch

import pytest

from personality_engine.registry import PersonalityRegistry
from personality_engine.schema import SCHEMA_VERSION, build_personality


def _make_chip():
    return build_personality({
        "schema": SCHEMA_VERSION,
        "identity": {
            "id": "registry-test",
            "name": "RegistryTest",
            "archetype": "builder",
        },
    })


def test_registry_ignores_non_object_state(tmp_path):
    registry_path = tmp_path / "personality_registry.json"
    registry_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    registry = PersonalityRegistry(registry_path)

    assert registry.get_assignments() == {}
    assert registry.get_personality("agent") is None


def test_registry_ignores_malformed_active_map(tmp_path):
    registry_path = tmp_path / "personality_registry.json"
    registry_path.write_text(
        json.dumps({"active": ["not", "a", "mapping"], "default": 42}),
        encoding="utf-8",
    )

    registry = PersonalityRegistry(registry_path)

    assert registry.get_assignments() == {}
    assert registry.get_personality("agent") is None


def test_registry_atomic_write_cleans_temp_file_after_replace_failure(tmp_path):
    registry_path = tmp_path / "personality_registry.json"
    old_payload = {"active": {"agent": "old"}, "default": None, "installed": []}
    registry_path.write_text(json.dumps(old_payload), encoding="utf-8")
    registry = PersonalityRegistry(registry_path)

    with patch("personality_engine.storage.os.replace", side_effect=OSError("boom")):
        with pytest.raises(OSError):
            registry.install(_make_chip())

    assert json.loads(registry_path.read_text(encoding="utf-8")) == old_payload
    assert list(tmp_path.glob("*.tmp")) == []
