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


def test_assign_unknown_personality_lists_installed_targets(tmp_path):
    registry = PersonalityRegistry(tmp_path / "personality_registry.json")
    registry.install(_make_chip())

    with pytest.raises(ValueError) as exc_info:
        registry.assign("agent-1", "ghost-personality")

    message = str(exc_info.value)
    assert "ghost-personality" in message
    assert "Installed personalities: registry-test." in message


def test_set_default_unknown_personality_lists_installed_targets(tmp_path):
    registry = PersonalityRegistry(tmp_path / "personality_registry.json")
    registry.install(_make_chip())

    with pytest.raises(ValueError) as exc_info:
        registry.set_default("ghost-personality")

    message = str(exc_info.value)
    assert "ghost-personality" in message
    assert "Installed personalities: registry-test." in message


def test_assign_unknown_personality_names_empty_registry_explicitly(tmp_path):
    registry = PersonalityRegistry(tmp_path / "personality_registry.json")

    with pytest.raises(ValueError) as exc_info:
        registry.assign("agent-1", "any-id")

    message = str(exc_info.value)
    assert "any-id" in message
    assert "Installed personalities: (none)." in message


def test_registry_restores_installed_chips_on_reload(tmp_path):
    """A registry written and reloaded must remember installed chips.

    Re-hydration reads the persisted ``installed`` array back into
    _installed (no filesystem rescan), so a fresh PersonalityRegistry
    pointed at the same JSON keeps assign()/get_personality() working
    after a process restart. The test stays isolated by using only the
    tmp_path registry file — it never reads the real ~/.spark home.
    """
    registry_path = tmp_path / "personality_registry.json"
    registry_a = PersonalityRegistry(registry_path)
    chip = _make_chip()
    registry_a.install(chip)
    registry_a.assign("agent-99", chip.id)

    # Confirm the persisted JSON carries the installed entry we rehydrate from.
    state = json.loads(registry_path.read_text(encoding="utf-8"))
    assert any(entry["id"] == chip.id for entry in state["installed"])

    registry_b = PersonalityRegistry(registry_path)
    reloaded = registry_b.get_personality("agent-99")
    assert reloaded is not None, "Registry must survive process restart"
    assert reloaded.id == chip.id
