from __future__ import annotations

import subprocess
import sys
import os
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_cli_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "personality_cli_under_test", ROOT / "scripts" / "personality_cli.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert "Did you mean" not in result.stdout


def test_personality_cli_command_typo_suggests_closest() -> None:
    result = _run_cli("activat")

    assert result.returncode == 1
    assert "Did you mean 'activate'?" in result.stdout


def test_personality_cli_help_exits_successfully() -> None:
    result = _run_cli("--help")

    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_personality_cli_no_args_is_a_usage_error() -> None:
    result = _run_cli()

    assert result.returncode == 1
    assert "Usage:" in result.stdout


def test_personality_cli_activate_without_id_is_a_usage_error() -> None:
    result = _run_cli("activate")

    assert result.returncode == 1
    assert "Usage: personality_cli.py activate" in result.stdout


def test_personality_cli_status_fails_for_missing_active_chip(tmp_path) -> None:
    active = tmp_path / ".spark" / "active_personality.json"
    active.parent.mkdir(parents=True)
    active.write_text('{"personality_id":"missing-chip"}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/personality_cli.py", "status"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "HOME": str(tmp_path)},
    )

    assert result.returncode == 1
    assert "could not load personality 'missing-chip'" in result.stdout


def test_personality_cli_activate_chip_typo_suggests_closest() -> None:
    result = _run_cli("activate", "artemiss")

    assert result.returncode == 1
    assert "Did you mean 'artemis'?" in result.stdout


def test_personality_cli_list_uses_singular_chip_label(monkeypatch, capsys) -> None:
    cli = _load_cli_module()
    chip = SimpleNamespace(
        id="one", name="One", archetype="sage", voice_signature="", tagline=""
    )
    monkeypatch.setattr(cli, "load_all_personalities", lambda: [chip])

    cli.cmd_list()

    assert "Found 1 personality chip:" in capsys.readouterr().out


def test_personality_cli_activate_names_empty_install_state(monkeypatch, capsys) -> None:
    cli = _load_cli_module()
    monkeypatch.setattr(cli, "load_all_personalities", lambda: [])

    with pytest.raises(SystemExit) as exc:
        cli.cmd_activate("missing")

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "No personality chips are installed yet." in output
    assert "Available personalities:" not in output


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
