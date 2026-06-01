from __future__ import annotations

import subprocess
import sys
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
