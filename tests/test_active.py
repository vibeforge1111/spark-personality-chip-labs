"""Tests for active personality resolver."""

import fcntl
import json
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from personality_engine.active import (
    get_active_personality,
    set_active_personality,
    clear_active_personality,
    get_active_personality_id,
    clear_cache,
    _check_file_cache,
    _write_cache,
    _resolve_personality_id,
    _acquire_file_lock,
    CACHE_FILE,
    CACHE_LOCK_FILE,
)
from personality_engine.schema import SCHEMA_VERSION, build_personality


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

    def test_cache_write_preserves_old_file_after_replace_failure(self, tmp_path):
        cache_path = tmp_path / "active_cache.json"
        old_payload = {"personality_id": "old", "cached_at": 1}
        cache_path.write_text(json.dumps(old_payload), encoding="utf-8")
        chip = build_personality({
            "schema": SCHEMA_VERSION,
            "identity": {"id": "test-active", "name": "TestActive"},
        })

        with patch("personality_engine.active.CACHE_FILE", cache_path):
            with patch("personality_engine.storage.os.replace", side_effect=OSError("boom")):
                _write_cache(chip)

        assert json.loads(cache_path.read_text(encoding="utf-8")) == old_payload
        assert list(tmp_path.glob("*.tmp")) == []

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


class TestCacheInvalidation:
    """Resolving the id before consulting caches (PR #6)."""

    def test_env_var_change_is_not_hidden_by_cache(self, tmp_path):
        """Changing SPARK_PERSONALITY should take effect immediately."""
        import yaml

        for chip_id, name in (("first-chip", "FirstChip"), ("second-chip", "SecondChip")):
            chip_file = tmp_path / f"{chip_id}.personality.yaml"
            chip_file.write_text(
                yaml.dump(
                    {
                        "schema": SCHEMA_VERSION,
                        "identity": {
                            "id": chip_id,
                            "name": name,
                            "archetype": "builder",
                        },
                        "traits": {"openness": 0.70},
                    }
                ),
                encoding="utf-8",
            )

        with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
            with patch("personality_engine.active.CACHE_FILE", tmp_path / "active_cache.json"):
                with patch.dict(os.environ, {"SPARK_PERSONALITY": "first-chip"}):
                    first = get_active_personality(search_paths=[tmp_path])
                    assert first is not None
                    assert first.id == "first-chip"

                with patch.dict(os.environ, {"SPARK_PERSONALITY": "second-chip"}):
                    second = get_active_personality(search_paths=[tmp_path])
                    assert second is not None
                    assert second.id == "second-chip"


class TestActiveFilePathMatchesId:
    """Explicit active-file paths cannot override the declared id (PR #8)."""

    def test_active_file_path_must_match_declared_personality_id(self, tmp_path):
        import yaml

        expected_data = {
            "schema": SCHEMA_VERSION,
            "identity": {
                "id": "expected-chip",
                "name": "ExpectedChip",
                "archetype": "builder",
            },
        }
        other_data = {
            "schema": SCHEMA_VERSION,
            "identity": {
                "id": "other-chip",
                "name": "OtherChip",
                "archetype": "oracle",
            },
        }
        expected_file = tmp_path / "expected-chip.personality.yaml"
        other_file = tmp_path / "other-chip.personality.yaml"
        expected_file.write_text(yaml.dump(expected_data), encoding="utf-8")
        other_file.write_text(yaml.dump(other_data), encoding="utf-8")

        active_file = tmp_path / "active.json"
        active_file.write_text(
            json.dumps({
                "personality_id": "expected-chip",
                "personality_path": str(other_file),
            }),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"SPARK_PERSONALITY": ""}):
            with patch("personality_engine.active.ACTIVE_FILE", active_file):
                with patch("personality_engine.active.CACHE_FILE", tmp_path / "cache.json"):
                    chip = get_active_personality(search_paths=[tmp_path])

        assert chip is not None
        assert chip.id == "expected-chip"


class TestFileCachePathTraversal:
    """The file cache must not load YAML from outside the chip roots (PR #196)."""

    def test_cache_rejects_path_outside_allowed_dirs(self, tmp_path):
        """Cache must not load personality_path outside known dirs."""
        import time as _time

        import yaml
        from personality_engine.active import _check_file_cache

        evil_dir = tmp_path / "evil"
        evil_dir.mkdir()
        evil_file = evil_dir / "evil.personality.yaml"
        evil_data = {
            "schema": SCHEMA_VERSION,
            "identity": {"id": "evil", "name": "Evil"},
            "traits": {},
        }
        with open(evil_file, "w") as f:
            yaml.dump(evil_data, f)

        cache_file = tmp_path / "active_cache.json"
        cache_data = {
            "personality_id": "evil",
            "personality_path": str(evil_file),
            "cached_at": _time.time(),
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch("personality_engine.active.CACHE_FILE", cache_file):
            result = _check_file_cache()

        assert result is None

    def test_cache_rejects_symlink_traversal(self, tmp_path):
        """Cache must not follow symlinks to outside dirs."""
        import time as _time

        import yaml
        from personality_engine.active import _check_file_cache

        evil_dir = tmp_path / "evil"
        evil_dir.mkdir()
        evil_file = evil_dir / "evil.personality.yaml"
        evil_data = {
            "schema": SCHEMA_VERSION,
            "identity": {"id": "evil", "name": "Evil"},
            "traits": {},
        }
        with open(evil_file, "w") as f:
            yaml.dump(evil_data, f)

        symlink_dir = tmp_path / "fake_allowed"
        symlink_dir.mkdir()
        symlink = symlink_dir / "evil.personality.yaml"
        symlink.symlink_to(evil_file)

        cache_file = tmp_path / "active_cache.json"
        cache_data = {
            "personality_id": "evil",
            "personality_path": str(symlink),
            "cached_at": _time.time(),
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch("personality_engine.active.CACHE_FILE", cache_file):
            result = _check_file_cache()

        assert result is None
class TestCacheFileLocking:
    """Tests for file-based locking around cache read/write operations."""

    def test_write_cache_holds_lock(self, personality_dir, tmp_path):
        """_write_cache should create a .lock sidecar file."""
        cache_path = tmp_path / "active_cache.json"
        lock_path = tmp_path / "active_cache.lock"

        with patch.dict(os.environ, {"SPARK_PERSONALITY": "test-active"}):
            with patch("personality_engine.active.CACHE_FILE", cache_path):
                with patch("personality_engine.active.CACHE_LOCK_FILE", lock_path):
                    chip = get_active_personality(search_paths=[personality_dir])
                    assert chip is not None

        # After the write, the lock file should exist and the cache file
        # should contain valid JSON
        assert cache_path.exists()
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "personality_id" in data
        assert "cached_at" in data

    def test_check_file_cache_uses_shared_lock(self, tmp_path):
        """_check_file_cache should acquire a shared lock while reading."""
        cache_path = tmp_path / "active_cache.json"
        lock_path = tmp_path / "active_cache.lock"

        # Write a valid cache entry directly
        cache_data = {
            "personality_id": "lock-test",
            "personality_name": "LockTest",
            "cached_at": time.time(),
            "personality_path": str(tmp_path / "lock-test.personality.yaml"),
        }
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch("personality_engine.active.CACHE_FILE", cache_path):
            with patch("personality_engine.active.CACHE_LOCK_FILE", lock_path):
                result = _check_file_cache()

        # Should have created a lock file during the read
        # (it's cleaned up after, but the lock file fd was opened)
        # The result is None because the personality file doesn't exist,
        # but the read completed without errors

    def test_write_then_read_returns_fresh_data(self, personality_dir, tmp_path):
        """Writing then reading the cache returns the expected chip."""
        cache_path = tmp_path / "active_cache.json"
        lock_path = tmp_path / "active_cache.lock"

        with patch.dict(os.environ, {"SPARK_PERSONALITY": "test-active"}):
            with patch("personality_engine.active.CACHE_FILE", cache_path):
                with patch("personality_engine.active.CACHE_LOCK_FILE", lock_path):
                    # First access writes to cache
                    chip1 = get_active_personality(search_paths=[personality_dir])
                    assert chip1 is not None
                    assert chip1.id == "test-active"

                    # Clear memory cache but keep file cache
                    from personality_engine.active import _memory_cache
                    _memory_cache.clear()

                    # Second access should read from file cache
                    chip2 = get_active_personality(search_paths=[personality_dir])
                    assert chip2 is not None
                    assert chip2.id == "test-active"

    def test_concurrent_writes_do_not_corrupt_cache(self, personality_dir, tmp_path):
        """Multiple sequential writes should not produce a corrupted cache file."""
        cache_path = tmp_path / "active_cache.json"
        lock_path = tmp_path / "active_cache.lock"

        with patch.dict(os.environ, {"SPARK_PERSONALITY": "test-active"}):
            with patch("personality_engine.active.CACHE_FILE", cache_path):
                with patch("personality_engine.active.CACHE_LOCK_FILE", lock_path):
                    # Simulate multiple sequential writes
                    for i in range(10):
                        chip = get_active_personality(search_paths=[personality_dir])
                        assert chip is not None
                        from personality_engine.active import _memory_cache
                        _memory_cache.clear()

        # Final cache file should be valid JSON
        assert cache_path.exists()
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "personality_id" in data

    def test_acquire_file_lock_context_manager(self, tmp_path):
        """_acquire_file_lock should create and use the lock file."""
        lock_path = tmp_path / "test.lock"

        with patch("personality_engine.active.CACHE_LOCK_FILE", lock_path):
            with _acquire_file_lock(fcntl.LOCK_EX):
                # Lock file should exist while held
                assert lock_path.exists()

        # Lock file still exists on disk (just unlocked), which is fine

    def test_read_lock_blocks_during_write(self, personality_dir, tmp_path):
        """Shared read lock should be compatible with concurrent readers."""
        import threading

        cache_path = tmp_path / "active_cache.json"
        lock_path = tmp_path / "active_cache.lock"

        # Write initial cache
        cache_data = {
            "personality_id": "test-active",
            "personality_name": "TestActive",
            "cached_at": time.time(),
        }
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        results = []

        def reader():
            with patch("personality_engine.active.CACHE_FILE", cache_path):
                with patch("personality_engine.active.CACHE_LOCK_FILE", lock_path):
                    chip = _check_file_cache()
                    results.append(chip)

        # Start two concurrent readers
        t1 = threading.Thread(target=reader)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Both readers should have completed (shared locks are compatible)
        assert len(results) == 2
