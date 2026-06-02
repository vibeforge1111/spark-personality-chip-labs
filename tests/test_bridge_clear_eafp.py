from __future__ import annotations

from pathlib import Path

from personality_engine.bridge import clear_bridge


def test_clear_bridge_missing_file_is_noop(tmp_path: Path) -> None:
    """clear_bridge must not raise FileNotFoundError when the bridge file is already gone.

    Race scenario: a parallel cleanup unlinks the bridge file between the
    pre-patch exists() probe and the unlink() call. Post-patch the call is
    a single atomic unlink(missing_ok=True), which is a no-op on a missing path.
    """
    missing = tmp_path / "no-such-bridge.json"
    assert not missing.exists()
    clear_bridge(missing)  # must not raise
    assert not missing.exists()


def test_clear_bridge_removes_existing_file(tmp_path: Path) -> None:
    """Happy-path regression: clear_bridge on an existing file unlinks it (post-condition preserved)."""
    present = tmp_path / "bridge.json"
    present.write_text("{}", encoding="utf-8")
    assert present.exists()
    clear_bridge(present)
    assert not present.exists()
