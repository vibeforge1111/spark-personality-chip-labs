"""Small JSON storage helpers for runtime state files."""

from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def state_namespace_key(personality_id: object) -> str:
    """Return a bounded, collision-resistant filename key for local state."""
    raw = personality_id if isinstance(personality_id, str) and personality_id else "default"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("._-").lower()
    slug = (slug or "personality")[:40]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


@contextmanager
def exclusive_file_lock(path: Path):
    """Hold a cross-process sidecar lock for a state-file transaction."""
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":  # pragma: no cover - exercised on Windows
            import msvcrt

            if lock_file.seek(0, os.SEEK_END) == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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
