"""
Active Personality Resolver

Determines which personality chip is active for the current session.
Resolution chain (first match wins):

1. SPARK_PERSONALITY env var        (e.g. "artemis")
2. ~/.spark/active_personality.json (e.g. {"personality_id": "artemis"})
3. Project-level .personality file  (contains personality id on first line)
4. None                             (no personality active)

Includes file-based caching with 5-minute TTL for fast hook lookups.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from .schema import PersonalityChip
from .storage import atomic_write_json

ACTIVE_FILE = Path.home() / ".spark" / "active_personality.json"
CACHE_FILE = Path.home() / ".cache" / "personality-chips" / "active_cache.json"
CACHE_TTL_SECONDS = 300  # 5 minutes

# Personality IDs are embedded in file paths and used as lookup keys, so they
# must not contain path separators or traversal sequences. The pattern is kept
# deliberately permissive (letters, digits, '_' and '-', any case, length 1-64)
# so it accepts legitimate custom ids while still rejecting '/', '\\', '.',
# whitespace and '..' — anything that could escape the chip directories.
_VALID_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _safe_personality_id(pid: object) -> Optional[str]:
    """Validate a personality id for safe use in path construction.

    Returns the trimmed id if it matches the expected format, else None.
    Prevents path-traversal via malicious personality_id values.
    """
    if not pid or not isinstance(pid, str):
        return None
    pid = pid.strip()
    if _VALID_ID_RE.match(pid):
        return pid
    return None


def _personality_roots() -> list[Path]:
    """Resolved directories a personality file is allowed to load from."""
    return [
        (Path.home() / ".spark" / "chips" / "personality").resolve(),
        (Path(__file__).parent.parent.parent / "personalities").resolve(),
    ]


def _is_within_roots(path: Path, roots: list[Path]) -> bool:
    """True if ``path`` is inside one of ``roots`` (real containment, not a
    string-prefix test — so a sibling like '<root>-evil' cannot escape)."""
    for root in roots:
        try:
            if path == root or path.is_relative_to(root):
                return True
        except (OSError, ValueError):
            continue
    return False


# In-memory cache for same-process reuse
_memory_cache: dict = {}


def get_active_personality(
    project_dir: str = None,
    search_paths: list[Path] = None,
) -> Optional[PersonalityChip]:
    """
    Resolve and load the active personality chip.

    Args:
        project_dir: Optional project directory to check for .personality file
        search_paths: Optional list of directories to search for personality files.
                      Defaults to ~/.spark/chips/personality/ and repo personalities/

    Returns:
        PersonalityChip if one is active, None otherwise.
    """
    # Resolve personality id BEFORE consulting caches so an env/project switch
    # takes effect immediately instead of returning a stale cached chip.
    personality_id, personality_path = _resolve_personality_id(project_dir)
    if not personality_id:
        return None

    # Check in-memory cache first
    cached = _check_memory_cache(expected_id=personality_id)
    if cached is not None:
        return cached

    # Check file cache
    cached = _check_file_cache(expected_id=personality_id)
    if cached is not None:
        _memory_cache["chip"] = cached
        _memory_cache["ts"] = time.time()
        return cached

    # Load the personality chip
    chip = _find_and_load(personality_id, personality_path, search_paths)
    if chip:
        _write_cache(chip)
        _memory_cache["chip"] = chip
        _memory_cache["ts"] = time.time()

    return chip


def set_active_personality(
    personality_id: str,
    personality_path: str = None,
) -> None:
    """
    Set the active personality by writing ~/.spark/active_personality.json.

    Args:
        personality_id: Personality chip id (e.g. "artemis")
        personality_path: Optional explicit path to the personality file
    """
    data = {"personality_id": personality_id}
    if personality_path:
        data["personality_path"] = str(personality_path)

    atomic_write_json(ACTIVE_FILE, data)

    # Clear caches so next get_active picks up the change
    clear_cache()


def clear_active_personality() -> None:
    """Remove the active personality setting."""
    # Use missing_ok=True so a concurrent clear (or pre-cleared state)
    # does not crash with FileNotFoundError; this matches the EAFP style
    # already used for CACHE_FILE.unlink() below.
    ACTIVE_FILE.unlink(missing_ok=True)
    clear_cache()


def get_active_personality_id(project_dir: str = None) -> Optional[str]:
    """
    Resolve just the personality ID without loading the chip.
    Useful for fast checks.
    """
    pid, _ = _resolve_personality_id(project_dir)
    return pid


def clear_cache() -> None:
    """Clear both memory and file caches."""
    _memory_cache.clear()
    if CACHE_FILE.exists():
        try:
            CACHE_FILE.unlink()
        except OSError:
            pass


# ── Resolution Chain ──

def _resolve_personality_id(project_dir: str = None) -> tuple[Optional[str], Optional[str]]:
    """
    Walk the resolution chain to find the active personality.
    Returns (personality_id, personality_path) or (None, None).
    """
    # 1. Environment variable
    env_id = _safe_personality_id(os.environ.get("SPARK_PERSONALITY", ""))
    if env_id:
        return env_id, None

    # 2. ~/.spark/active_personality.json
    if ACTIVE_FILE.exists():
        try:
            with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            pid = _safe_personality_id(data.get("personality_id", ""))
            ppath = data.get("personality_path")
            if pid:
                return pid, ppath
        except (json.JSONDecodeError, IOError):
            pass

    # 3. Project-level .personality file
    if project_dir:
        dot_file = Path(project_dir) / ".personality"
        if dot_file.exists():
            try:
                # Guard against oversized files — only the first line is needed.
                if dot_file.stat().st_size > 4096:
                    return None, None
                pid = _safe_personality_id(
                    dot_file.read_text(encoding="utf-8").strip().split("\n")[0].strip()
                )
                if pid:
                    return pid, None
            except (IOError, OSError):
                pass

    # 4. Nothing active
    return None, None


# ── Loading ──

def _find_and_load(
    personality_id: str,
    personality_path: str = None,
    search_paths: list[Path] = None,
) -> Optional[PersonalityChip]:
    """Find and load a personality chip by id."""
    from .loader import load_personality

    # If explicit path given, try it first — but only from inside the known
    # personality roots (path-traversal / arbitrary-YAML guard), and only if
    # the loaded chip's declared id matches the resolved id (an explicit path
    # cannot override which personality is active).
    if personality_path:
        p = Path(personality_path).resolve()
        if p.exists() and _is_within_roots(p, _personality_roots()):
            try:
                chip = load_personality(p)
                if chip.id == personality_id:
                    return chip
            except (ValueError, FileNotFoundError):
                pass

    # Search standard locations
    if search_paths is None:
        search_paths = [
            Path.home() / ".spark" / "chips" / "personality",
            Path(__file__).parent.parent.parent / "personalities",
        ]

    for search_dir in search_paths:
        if not search_dir.exists():
            continue

        # Try: {id}.personality.yaml
        single = search_dir / f"{personality_id}.personality.yaml"
        if single.exists():
            try:
                return load_personality(single)
            except (ValueError, FileNotFoundError):
                pass

        # Try: {id}/personality.yaml
        dir_format = search_dir / personality_id / "personality.yaml"
        if dir_format.exists():
            try:
                return load_personality(search_dir / personality_id)
            except (ValueError, FileNotFoundError):
                pass

    return None


# ── Caching ──

def _check_memory_cache(expected_id: Optional[str] = None) -> Optional[PersonalityChip]:
    """Check in-memory cache (same process only)."""
    if "chip" not in _memory_cache:
        return None
    ts = _memory_cache.get("ts", 0)
    if time.time() - ts > CACHE_TTL_SECONDS:
        _memory_cache.clear()
        return None
    chip = _memory_cache["chip"]
    if expected_id and chip.id != expected_id:
        return None
    return chip


def _check_file_cache(expected_id: Optional[str] = None) -> Optional[PersonalityChip]:
    """Check file-based cache for cross-process reuse."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    # Check TTL – delete stale file so we don't keep re-parsing it
    cached_at = data.get("cached_at", 0)
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        try:
            CACHE_FILE.unlink()
        except OSError:
            pass
        return None

    # Don't serve a cache entry for a different personality than requested.
    if expected_id and data.get("personality_id") != expected_id:
        return None

    # Rebuild chip from cached path — only from inside the known personality
    # roots so a tampered cache cannot make us load arbitrary YAML. Use real
    # containment (is_relative_to), not a string-prefix test that a sibling
    # like '<root>-evil' could slip past.
    path = data.get("personality_path")
    if path:
        resolved = Path(path).resolve()
        if resolved.exists() and _is_within_roots(resolved, _personality_roots()):
            from .loader import load_personality
            try:
                return load_personality(resolved)
            except (ValueError, FileNotFoundError):
                return None

    return None


def _write_cache(chip: PersonalityChip) -> None:
    """Write chip info to file cache."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    # Find the source path from _raw if available
    raw = chip._raw
    data = {
        "personality_id": chip.id,
        "personality_name": chip.name,
        "cached_at": time.time(),
    }

    # Try to find the original file path for fast reload
    # Check standard locations
    for search_dir in [
        Path.home() / ".spark" / "chips" / "personality",
        Path(__file__).parent.parent.parent / "personalities",
    ]:
        single = search_dir / f"{chip.id}.personality.yaml"
        if single.exists():
            data["personality_path"] = str(single)
            break
        dir_format = search_dir / chip.id / "personality.yaml"
        if dir_format.exists():
            data["personality_path"] = str(search_dir / chip.id)
            break

    atomic_write_json(CACHE_FILE, data, raise_on_error=False)
