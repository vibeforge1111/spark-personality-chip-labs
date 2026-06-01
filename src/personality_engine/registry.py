"""
Personality Chip Registry

Tracks installed and active personality chips.
Follows the same pattern as Spark Intelligence Builder's ChipRegistry.

Storage: ~/.spark/personality_registry.json
"""

from pathlib import Path
from typing import Optional

from .loader import load_personality, load_all_personalities
from .schema import PersonalityChip
from .storage import atomic_write_json, read_json_object

REGISTRY_FILE = Path.home() / ".spark" / "personality_registry.json"


class PersonalityRegistry:
    """
    Registry of installed personality chips.

    Tracks:
    - Which personalities are installed
    - Which personality is active per agent/project
    - Global default personality
    """

    def __init__(self, registry_path: Path = REGISTRY_FILE):
        self._path = registry_path
        self._installed: dict[str, PersonalityChip] = {}
        self._active: dict[str, str] = {}  # agent_id → personality_id
        self._default: Optional[str] = None
        self._load_state()

    def install(self, chip: PersonalityChip) -> None:
        """Register a personality chip as available."""
        self._installed[chip.id] = chip
        self._save_state()

    def uninstall(self, personality_id: str) -> None:
        """Remove a personality chip from the registry."""
        self._installed.pop(personality_id, None)
        # Remove any active assignments using this personality
        self._active = {
            agent: pid for agent, pid in self._active.items()
            if pid != personality_id
        }
        if self._default == personality_id:
            self._default = None
        self._save_state()

    def assign(self, agent_id: str, personality_id: str) -> None:
        """Assign a personality to an agent."""
        if personality_id not in self._installed:
            raise ValueError(f"Personality '{personality_id}' not installed")
        self._active[agent_id] = personality_id
        self._save_state()

    def unassign(self, agent_id: str) -> None:
        """Remove personality assignment from an agent."""
        self._active.pop(agent_id, None)
        self._save_state()

    def get_personality(self, agent_id: str) -> Optional[PersonalityChip]:
        """Get the personality chip assigned to an agent."""
        pid = self._active.get(agent_id) or self._default
        if pid:
            return self._installed.get(pid)
        return None

    def set_default(self, personality_id: str) -> None:
        """Set the global default personality for agents without assignment."""
        if personality_id not in self._installed:
            raise ValueError(f"Personality '{personality_id}' not installed")
        self._default = personality_id
        self._save_state()

    def get_installed(self) -> list[PersonalityChip]:
        """List all installed personality chips."""
        return list(self._installed.values())

    def get_assignments(self) -> dict[str, str]:
        """Get all agent → personality assignments."""
        return dict(self._active)

    def scan_and_install(self, directory: str | Path = None) -> int:
        """
        Scan a directory for personality chips and install them.
        Returns count of newly installed chips.
        """
        chips = load_all_personalities(directory)
        count = 0
        for chip in chips:
            if chip.id not in self._installed:
                self._installed[chip.id] = chip
                count += 1
        if count > 0:
            self._save_state()
        return count

    def _load_state(self) -> None:
        """Load registry state from disk."""
        state = read_json_object(self._path)
        if state is None:
            return
        active = state.get("active", {})
        self._active = active if isinstance(active, dict) else {}
        default = state.get("default")
        self._default = default if isinstance(default, str) else None

    def _save_state(self) -> None:
        """Persist registry state to disk."""
        state = {
            "active": self._active,
            "default": self._default,
            "installed": [
                {"id": chip.id, "name": chip.name, "archetype": chip.archetype}
                for chip in self._installed.values()
            ],
        }
        atomic_write_json(self._path, state)
