"""Small JSON storage helpers for runtime state files."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json_object(path: Path) -> dict[str, Any] | None:
    """Read a JSON object from disk, returning None for missing or invalid state."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def atomic_write_json(
    path: Path,
    payload: dict[str, Any],
    *,
    raise_on_error: bool = True,
) -> bool:
    """Write a JSON object atomically and clean up partial temp files on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    tmp_path: Path | None = None
    try:
        fd, raw_tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        tmp_path = Path(raw_tmp_path)
        os.write(fd, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.replace(str(tmp_path), str(path))
        tmp_path = None
        return True
    except OSError:
        if raise_on_error:
            raise
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
