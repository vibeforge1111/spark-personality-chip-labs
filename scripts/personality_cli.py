#!/usr/bin/env python3
"""Personality Chip CLI

Simple CLI for activating/deactivating personality chips.

Usage:
    python scripts/personality_cli.py list                # Show available personalities
    python scripts/personality_cli.py activate artemis     # Set active personality
    python scripts/personality_cli.py deactivate           # Clear active personality
    python scripts/personality_cli.py status               # Show current state
    python scripts/personality_cli.py bridge                # Show bridge payload
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personality_engine.loader import load_all_personalities, load_personality
from personality_engine.active import (
    get_active_personality_id,
    get_active_personality,
    set_active_personality,
    clear_active_personality,
    ACTIVE_FILE,
)
from personality_engine.bridge import build_bridge_payload, read_bridge, BRIDGE_FILE


def cmd_list():
    """List all available personality chips."""
    chips = load_all_personalities()
    if not chips:
        print("No personality chips found.")
        print("Place .personality.yaml files in personalities/ or ~/.spark/chips/personality/")
        return

    print(f"Found {len(chips)} personality chip(s):\n")
    for chip in chips:
        print(f"  {chip.id}")
        print(f"    Name:      {chip.name}")
        print(f"    Archetype: {chip.archetype}")
        if chip.voice_signature:
            print(f"    Voice:     {chip.voice_signature}")
        if chip.tagline:
            print(f"    Tagline:   {chip.tagline}")
        print()


def cmd_activate(personality_id: str):
    """Activate a personality chip."""
    # Try to find the personality first
    chips = load_all_personalities()
    match = None
    for chip in chips:
        if chip.id == personality_id:
            match = chip
            break

    if not match:
        print(f"Personality '{personality_id}' not found.")
        print("Available personalities:")
        for chip in chips:
            print(f"  - {chip.id}")
        sys.exit(1)

    set_active_personality(personality_id)
    print(f"Activated personality: {match.name} ({match.id})")
    print(f"  Archetype: {match.archetype}")
    if match.voice_signature:
        print(f"  Voice: {match.voice_signature}")
    print(f"\nWritten to: {ACTIVE_FILE}")


def cmd_deactivate():
    """Clear the active personality."""
    current = get_active_personality_id()
    clear_active_personality()
    if current:
        print(f"Deactivated personality: {current}")
    else:
        print("No personality was active.")


def cmd_status():
    """Show current personality state."""
    pid = get_active_personality_id()
    print("Personality Chip Status")
    print("=" * 40)

    if pid:
        print(f"Active personality: {pid}")
        chip = get_active_personality()
        if chip:
            print(f"  Name:      {chip.name}")
            print(f"  Archetype: {chip.archetype}")
            if chip.voice_signature:
                print(f"  Voice:     {chip.voice_signature}")
        else:
            print(f"  (could not load personality '{pid}')")
    else:
        print("Active personality: None")

    print(f"\nActive file: {ACTIVE_FILE}")
    print(f"  Exists: {ACTIVE_FILE.exists()}")

    print(f"\nBridge file: {BRIDGE_FILE}")
    print(f"  Exists: {BRIDGE_FILE.exists()}")

    bridge = read_bridge()
    if bridge:
        stale = bridge.pop("_stale", False)
        print(f"  Schema: {bridge.get('schema_version', 'unknown')}")
        print(f"  Source: {bridge.get('source', 'unknown')}")
        meta = bridge.get("meta", {})
        print(f"  Personality: {meta.get('personality_name', 'unknown')}")
        print(f"  Stale: {stale}")


def cmd_bridge():
    """Show the current bridge payload."""
    chip = get_active_personality()
    if not chip:
        print("No active personality. Use 'activate' first.")
        sys.exit(1)

    payload = build_bridge_payload(chip)
    print(json.dumps(payload, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].strip().lower()

    if command == "list":
        cmd_list()
    elif command == "activate":
        if len(sys.argv) < 3:
            print("Usage: personality_cli.py activate <personality_id>")
            sys.exit(1)
        cmd_activate(sys.argv[2])
    elif command == "deactivate":
        cmd_deactivate()
    elif command == "status":
        cmd_status()
    elif command == "bridge":
        cmd_bridge()
    else:
        print(f"Unknown command: {command}")
        print("Available: list, activate, deactivate, status, bridge")
        sys.exit(1)


if __name__ == "__main__":
    main()
