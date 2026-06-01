"""
Personality Chip Loader

Loads .personality.yaml files from disk.
Supports two formats matching Spark chip conventions:

1. Single file:  {id}.personality.yaml
2. Directory:    {id}/personality.yaml  (+ optional overlay files)

Directory format allows modular overrides:
  {id}/
  ├── personality.yaml       # Core personality
  ├── traits.yaml             # Override OCEAN traits
  ├── emotional.yaml          # Override emotional profile
  ├── preferences.yaml        # Override preferences
  ├── adaptive.yaml           # Override adaptive behaviors
  └── custom.yaml             # Any custom sections (merged in)
"""

import os
from pathlib import Path
from typing import Optional

from .schema import PersonalityChip, validate_personality, build_personality

try:
    import yaml
except ImportError:
    yaml = None  # Handled in _load_yaml

_RECOVERABLE_OVERLAY_ERRORS = (OSError, ValueError) + ((yaml.YAMLError,) if yaml is not None else ())


def load_personality(path: str | Path) -> Optional[PersonalityChip]:
    """
    Load a personality chip from a file or directory.

    Args:
        path: Path to .personality.yaml file or directory containing personality.yaml

    Returns:
        PersonalityChip if valid, None if validation fails.

    Raises:
        FileNotFoundError: If path doesn't exist.
        ValueError: If YAML parsing fails or validation errors found.
    """
    path = Path(path)

    if path.is_dir():
        spec = _load_directory(path)
    elif path.is_file():
        spec = _load_yaml(path)
    else:
        raise FileNotFoundError(f"Personality chip not found: {path}")

    errors = validate_personality(spec)
    if errors:
        raise ValueError(
            f"Personality chip validation failed for {path}:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    return build_personality(spec)


def load_all_personalities(
    directory: str | Path = None,
) -> list[PersonalityChip]:
    """
    Load all personality chips from a directory.

    Default search path: ~/.spark/chips/personality/
    Falls back to personalities/ in the repo root.

    Returns:
        List of valid PersonalityChip objects (invalid chips are skipped with warning).
    """
    if directory is None:
        spark_dir = Path.home() / ".spark" / "chips" / "personality"
        if spark_dir.exists():
            directory = spark_dir
        else:
            directory = Path(__file__).parent.parent.parent / "personalities"

    directory = Path(directory)
    if not directory.exists():
        return []

    chips = []
    for entry in sorted(directory.iterdir()):
        try:
            if entry.is_file() and entry.name.endswith(".personality.yaml") and not entry.name.startswith("_"):
                chip = load_personality(entry)
                if chip:
                    chips.append(chip)
            elif entry.is_dir() and (entry / "personality.yaml").exists():
                chip = load_personality(entry)
                if chip:
                    chips.append(chip)
        except (ValueError, FileNotFoundError) as e:
            print(f"[personality-loader] Skipping {entry.name}: {e}")

    return chips


def _load_directory(directory: Path) -> dict:
    """
    Load a directory-format personality chip.
    Merges personality.yaml with optional overlay files.
    """
    base_file = directory / "personality.yaml"
    if not base_file.exists():
        raise FileNotFoundError(f"No personality.yaml in {directory}")

    spec = _load_yaml(base_file)

    # Overlay files — each merges into a specific section
    overlay_map = {
        "traits.yaml": "traits",
        "emotional.yaml": "emotional_profile",
        "preferences.yaml": "preferences",
        "adaptive.yaml": "adaptive",
        "consciousness.yaml": "consciousness",
        "safety.yaml": "safety",
        "vulnerabilities.yaml": "vulnerabilities",
        "strengths.yaml": "strengths",
    }

    for filename, section_key in overlay_map.items():
        overlay_path = directory / filename
        if overlay_path.exists():
            try:
                overlay_data = _load_yaml(overlay_path)
            except _RECOVERABLE_OVERLAY_ERRORS:
                continue
            if isinstance(overlay_data, dict):
                # For list sections (vulnerabilities, strengths), replace entirely
                if section_key in ("vulnerabilities", "strengths"):
                    items = overlay_data.get(section_key, overlay_data)
                    spec[section_key] = items if isinstance(items, list) else [items]
                else:
                    existing = spec.get(section_key, {})
                    if isinstance(existing, dict) and isinstance(overlay_data, dict):
                        # Use the section key if present, otherwise use root
                        merge_data = overlay_data.get(section_key, overlay_data)
                        if isinstance(merge_data, dict):
                            existing.update(merge_data)
                            spec[section_key] = existing
                        else:
                            spec[section_key] = merge_data

    # Custom overlay — merges at root level for any extra sections
    custom_path = directory / "custom.yaml"
    if custom_path.exists():
        custom_data = _load_yaml(custom_path)
        if isinstance(custom_data, dict):
            for key, value in custom_data.items():
                if key not in spec:
                    spec[key] = value

    return spec


def _load_yaml(path: Path) -> dict:
    """Load and parse a YAML file."""
    if yaml is None:
        raise ImportError(
            "PyYAML is required: pip install pyyaml"
        )

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping, got {type(data).__name__}")

    return data
