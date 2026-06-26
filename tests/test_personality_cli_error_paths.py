"""CLI error-path tests for scripts/personality_cli.py.

The existing test_personality_cli_script.py pins the happy-path
status / list / unknown-command behavior. The argument-validation
paths (no args -> usage doc, activate with no id -> usage line, activate
with unknown id -> not-found message) and the structured-output paths
are unpinned. These error paths matter because a user typing the wrong
incantation should get a clear exit code 1 instead of crashing or
silently doing nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/personality_cli.py", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_no_args_prints_usage_and_exits_one() -> None:
    result = _run_cli()
    assert result.returncode == 1
    # The docstring usage line is what main() prints when len(argv) < 2.
    assert "personality_cli.py" in result.stdout


def test_activate_without_id_prints_usage_line_and_exits_one() -> None:
    result = _run_cli("activate")
    assert result.returncode == 1
    assert "Usage: personality_cli.py activate" in result.stdout


def test_activate_unknown_id_lists_available_and_exits_one() -> None:
    result = _run_cli("activate", "not-a-real-personality-id-xyz")
    assert result.returncode == 1
    assert "not found" in result.stdout
    # Shows the available list to help the user recover.
    assert "Available personalities" in result.stdout


def test_list_command_returns_zero_and_does_not_error() -> None:
    result = _run_cli("list")
    assert result.returncode == 0
    # Either there is a personalities header or the empty-state message.
    assert (
        "personality chip" in result.stdout.lower()
        or "No personality chips found" in result.stdout
    )


def test_status_command_returns_zero_and_prints_header() -> None:
    result = _run_cli("status")
    assert result.returncode == 0
    assert "Personality Chip Status" in result.stdout


@pytest.mark.parametrize("variant", ["LIST", "Activate", "  status  ", "List"])
def test_known_commands_remain_case_and_whitespace_tolerant(variant: str) -> None:
    # Existing test_personality_cli_script.py covers 'Status' specifically;
    # widen to the full known-command set so a regression to the
    # .strip().lower() normalization cannot silently break some variants
    # while leaving status working.
    if variant.strip().lower() == "activate":
        # Activate without id still exits 1 with the usage line — the
        # normalization succeeded if we hit the usage line, not "Unknown".
        result = _run_cli(variant)
        assert "Unknown command" not in result.stdout
    else:
        result = _run_cli(variant)
        assert result.returncode == 0
        assert "Unknown command" not in result.stdout
