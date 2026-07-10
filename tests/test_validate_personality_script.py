from __future__ import annotations

import re
import subprocess
import sys
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
    assert match, f"Expected 'Results: N/N passed' in output, got: {result.stdout}"
    passed, total = int(match.group(1)), int(match.group(2))
    assert passed == total, f"Not all personality chips passed: {passed}/{total}"
