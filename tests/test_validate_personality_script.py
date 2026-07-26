from __future__ import annotations

import subprocess
import sys
import re
import os
import site
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_validate_personality_empty_directory_fails(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_personality.py", str(tmp_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "no personality chips found" in result.stdout
    assert "Expected *.personality.yaml files" in result.stdout


def test_validate_personality_help_exits_successfully() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_personality.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_validate_personality_fixture_directory_still_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_personality.py", "personalities"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    match = re.search(r"Results: (\d+)/(\d+) passed", result.stdout)
    assert match
    assert match.group(1) == match.group(2)


def test_validate_personality_verbose_output_file(tmp_path: Path) -> None:
    report = tmp_path / "nested" / "report.txt"
    result = subprocess.run(
        [sys.executable, "scripts/validate_personality.py", "--verbose", "--output", str(report), "personalities"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    content = report.read_text(encoding="utf-8")
    assert "Context Preview" in content
    assert "Bridge Payload Summary" in content
    assert re.search(r"Results: (\d+)/(\d+) passed", content)


def test_validate_personality_expands_home_in_target(tmp_path: Path) -> None:
    target = tmp_path / "chip.personality.yaml"
    target.write_text((ROOT / "personalities" / "artemis.personality.yaml").read_text(), encoding="utf-8")
    pythonpath = os.pathsep.join(
        filter(None, [site.getusersitepackages(), os.environ.get("PYTHONPATH", "")])
    )
    result = subprocess.run(
        [sys.executable, "scripts/validate_personality.py", "~/chip.personality.yaml"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "HOME": str(tmp_path), "PYTHONPATH": pythonpath},
    )

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_validate_personality_refuses_to_overwrite_target() -> None:
    target = "personalities/artemis.personality.yaml"
    result = subprocess.run(
        [sys.executable, "scripts/validate_personality.py", "--output", target, target],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "must not overwrite" in result.stderr
