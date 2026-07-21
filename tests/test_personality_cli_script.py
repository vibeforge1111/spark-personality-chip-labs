from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/personality_cli.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_personality_cli_status_lowercase_matches() -> None:
    result = _run_cli("status")

    assert result.returncode == 0
    assert "Unknown command" not in result.stdout


def test_personality_cli_status_mixed_case_reaches_handler() -> None:
    result = _run_cli("Status")

    assert result.returncode == 0
    assert "Unknown command" not in result.stdout


def test_personality_cli_list_with_surrounding_whitespace() -> None:
    result = _run_cli("  list  ")

    assert result.returncode == 0
    assert "Unknown command" not in result.stdout


def test_personality_cli_truly_unknown_command_still_errors() -> None:
    result = _run_cli("frobnicate")

    assert result.returncode == 1
    assert "Unknown command: frobnicate" in result.stdout


def test_personality_cli_deactivate_clears_active_and_bridge_files(tmp_path) -> None:
    active = tmp_path / ".spark" / "active_personality.json"
    bridge = tmp_path / ".spark" / "bridges" / "consciousness" / "emotional_context.v1.json"
    active.parent.mkdir(parents=True)
    bridge.parent.mkdir(parents=True)
    active.write_text('{"personality_id": "stale"}', encoding="utf-8")
    bridge.write_text('{"schema_version": "bridge.v1"}', encoding="utf-8")
    env = {**os.environ, "HOME": str(tmp_path)}

    result = subprocess.run(
        [sys.executable, "scripts/personality_cli.py", "deactivate"],
        cwd=ROOT, text=True, capture_output=True, check=False, env=env,
    )

    assert result.returncode == 0
    assert not active.exists()
    assert not bridge.exists()
