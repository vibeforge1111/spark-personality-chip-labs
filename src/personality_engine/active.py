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
import time
from pathlib import Path
from typing import Optional

from .schema import PersonalityChip

ACTIVE_FILE = Path.home() / ".spark" / "active_personality.json"
CACHE_FILE = Path.home() / ".cache" / "personality-chips" / "active_cache.json"
CACHE_TTL_SECONDS = 300  # 5 minutes

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
    # Check in-memory cache first
    cached = _check_memory_cache()
    if cached is not None:
        return cached

    # Check file cache
    cached = _check_file_cache()
    if cached is not None:
        _memory_cache["chip"] = cached
        _memory_cache["ts"] = time.time()
        return cached

    # Resolve personality id
    personality_id, personality_path = _resolve_personality_id(project_dir)
    if not personality_id:
        return None

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
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {"personality_id": personality_id}
    if personality_path:
        data["personality_path"] = str(personality_path)

    with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Clear caches so next get_active picks up the change
    clear_cache()


def clear_active_personality() -> None:
    """Remove the active personality setting."""
    if ACTIVE_FILE.exists():
        ACTIVE_FILE.unlink()
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
    env_id = os.environ.get("SPARK_PERSONALITY", "").strip()
    if env_id:
        return env_id, None

    # 2. Global active file
    if ACTIVE_FILE.exists():
        try:
            with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            pid = data.get("personality_id", "").strip()
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
                pid = dot_file.read_text(encoding="utf-8").strip().split("\n")[0].strip()
                if pid:
                    return pid, None
            except IOError:
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

    # If explicit path given, try it first
    if personality_path:
        p = Path(personality_path)
        if p.exists():
            try:
                return load_personality(p)
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

def _check_memory_cache() -> Optional[PersonalityChip]:
    """Check in-memory cache (same process only)."""
    if "chip" not in _memory_cache:
        return None
    ts = _memory_cache.get("ts", 0)
    if time.time() - ts > CACHE_TTL_SECONDS:
        _memory_cache.clear()
        return None
    return _memory_cache["chip"]


def _check_file_cache() -> Optional[PersonalityChip]:
    """Check file-based cache for cross-process reuse."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    # Check TTL
    cached_at = data.get("cached_at", 0)
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        return None

    # Rebuild chip from cached path
    path = data.get("personality_path")
    if path and Path(path).exists():
        from .loader import load_personality
        try:
            return load_personality(Path(path))
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

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except IOError:
        pass
