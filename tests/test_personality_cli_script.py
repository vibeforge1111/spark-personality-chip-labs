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
    # Sanity: the documented subcommand reaches cmd_status().
    assert "Unknown command" not in result.stdout


def test_personality_cli_status_mixed_case_reaches_handler() -> None:
    # Pre-fix: `Status` (capitalized) fell into the "Unknown command" branch
    # and exited 1 because the equality compare was case-sensitive.
    result = _run_cli("Status")
    assert result.returncode == 0, (
        f"mixed-case subcommand should reach handler, got returncode "
        f"{result.returncode}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "Unknown command" not in result.stdout


def test_personality_cli_list_with_surrounding_whitespace() -> None:
    # A leading/trailing space in the argument (e.g. copy-paste artefacts)
    # should not trip the dispatcher.
    result = _run_cli("  list  ")
    assert result.returncode == 0
    assert "Unknown command" not in result.stdout


def test_personality_cli_truly_unknown_command_still_errors() -> None:
    # The "Unknown command" branch should still fire for non-matching input.
    result = _run_cli("frobnicate")
    assert result.returncode == 1
    assert "Unknown command: frobnicate" in result.stdout
