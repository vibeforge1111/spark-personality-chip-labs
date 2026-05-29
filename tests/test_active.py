"""Tests for active personality resolver."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from personality_engine.active import (
    get_active_personality,
    set_active_personality,
    clear_active_personality,
    get_active_personality_id,
    clear_cache,
    _resolve_personality_id,
)
from personality_engine.schema import SCHEMA_VERSION


@pytest.fixture(autouse=True)
def clean_caches():
    """Clear caches before and after each test."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def personality_dir(tmp_path):
    """Create a temp directory with a test personality file."""
    import yaml

    chip_data = {
        "schema": SCHEMA_VERSION,
        "identity": {
            "id": "test-active",
            "name": "TestActive",
            "archetype": "builder",
        },
        "traits": {"openness": 0.70},
    }

    chip_file = tmp_path / "test-active.personality.yaml"
    with open(chip_file, "w", encoding="utf-8") as f:
        yaml.dump(chip_data, f)

    return tmp_path


class TestResolveChain:

    def test_env_var_wins(self, tmp_path):
        """SPARK_PERSONALITY env var takes priority."""
        with patch.dict(os.environ, {"SPARK_PERSONALITY": "my-agent"}):
            pid, ppath = _resolve_personality_id()
            assert pid == "my-agent"
            assert ppath is None

    def test_active_file(self, tmp_path):
        """~/.spark/active_personality.json is second priority."""
        active_file = tmp_path / "active.json"
        with open(active_file, "w") as f:
            json.dump({"personality_id": "artemis", "personality_path": "/some/path"}, f)

        with patch("personality_engine.active.ACTIVE_FILE", active_file):
            pid, ppath = _resolve_personality_id()
            assert pid == "artemis"
            assert ppath == "/some/path"

    def test_project_dotfile(self, tmp_path):
        """Project .personality file is third priority."""
        dot_file = tmp_path / ".personality"
        dot_file.write_text("forge\n")

        with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
            pid, ppath = _resolve_personality_id(project_dir=str(tmp_path))
            assert pid == "forge"

    def test_nothing_active(self, tmp_path):
        """Returns None when nothing is configured."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove SPARK_PERSONALITY if set
            os.environ.pop("SPARK_PERSONALITY", None)
            with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
                pid, ppath = _resolve_personality_id()
                assert pid is None
                assert ppath is None

    def test_env_var_empty_skipped(self, tmp_path):
        """Empty SPARK_PERSONALITY is treated as unset."""
        with patch.dict(os.environ, {"SPARK_PERSONALITY": "  "}):
            with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
                pid, _ = _resolve_personality_id()
                # Empty string should be skipped (stripped to "")
                assert pid is None or pid == ""


class TestGetActivePersonality:

    def test_loads_from_env(self, personality_dir):
        """Full load from env var."""
        with patch.dict(os.environ, {"SPARK_PERSONALITY": "test-active"}):
            chip = get_active_personality(search_paths=[personality_dir])
            assert chip is not None
            assert chip.id == "test-active"
            assert chip.name == "TestActive"

    def test_cache_parent_file_does_not_block_active_personality(self, personality_dir, tmp_path):
        """Cache write failures should not prevent loading a valid active chip."""
        cache_parent = tmp_path / "active_cache_parent"
        cache_parent.write_text("not a directory", encoding="utf-8")

        with patch.dict(os.environ, {"SPARK_PERSONALITY": "test-active"}):
            with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
                with patch("personality_engine.active.CACHE_FILE", cache_parent / "active_cache.json"):
                    chip = get_active_personality(search_paths=[personality_dir])

        assert chip is not None
        assert chip.id == "test-active"

    def test_returns_none_when_not_found(self, tmp_path):
        """Returns None when personality id doesn't match any file."""
        with patch.dict(os.environ, {"SPARK_PERSONALITY": "nonexistent"}):
            with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
                chip = get_active_personality(search_paths=[tmp_path])
                assert chip is None

    def test_returns_none_when_nothing_active(self, tmp_path):
        """Returns None when no personality is configured."""
        os.environ.pop("SPARK_PERSONALITY", None)
        with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
            chip = get_active_personality(search_paths=[tmp_path])
            assert chip is None


class TestSetAndClear:

    def test_set_active(self, tmp_path):
        """set_active_personality writes the active file."""
        active_file = tmp_path / "active.json"
        with patch("personality_engine.active.ACTIVE_FILE", active_file):
            set_active_personality("forge", personality_path="/path/to/forge")

        data = json.loads(active_file.read_text())
        assert data["personality_id"] == "forge"
        assert data["personality_path"] == "/path/to/forge"

    def test_clear_active(self, tmp_path):
        """clear_active_personality removes the active file."""
        active_file = tmp_path / "active.json"
        active_file.write_text("{}")

        with patch("personality_engine.active.ACTIVE_FILE", active_file):
            clear_active_personality()

        assert not active_file.exists()


class TestGetActivePersonalityId:

    def test_returns_id_from_env(self):
        with patch.dict(os.environ, {"SPARK_PERSONALITY": "echo"}):
            assert get_active_personality_id() == "echo"

    def test_returns_none_when_unset(self, tmp_path):
        os.environ.pop("SPARK_PERSONALITY", None)
        with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
            assert get_active_personality_id() is None
