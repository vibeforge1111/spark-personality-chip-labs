from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_unknown_subcommand_lists_known_subcommands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "personality_engine", "hoks", "session_start"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={
            "PYTHONPATH": "src",
            "PATH": "/usr/bin:/usr/local/bin:/bin",
        },
    )

    assert result.returncode == 1
    assert "Unknown subcommand" in result.stderr
    assert "hoks" in result.stderr
    assert "Known subcommands: hooks" in result.stderr


def test_unknown_subcommand_does_not_consume_third_arg_as_hook_name() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "personality_engine", "wrong", "session_start"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={
            "PYTHONPATH": "src",
            "PATH": "/usr/bin:/usr/local/bin:/bin",
        },
    )

    assert result.returncode == 1
    # The hook handler should not have run, so its 'Unknown hook' message
    # must not appear.
    assert "Unknown hook" not in result.stderr
    assert "Unknown hook" not in result.stdout
