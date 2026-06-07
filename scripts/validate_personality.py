#!/usr/bin/env python3
"""
Validate a personality chip YAML file.

Usage:
    python scripts/validate_personality.py personalities/artemis.personality.yaml
    python scripts/validate_personality.py personalities/  # validate all in directory
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personality_engine.loader import load_personality, load_all_personalities
from personality_engine.context import build_personality_context
from personality_engine.bridge import build_bridge_payload


def validate_file(path: Path) -> bool:
    """Validate a single personality chip and print summary."""
    try:
        chip = load_personality(path)
    except (ValueError, FileNotFoundError) as e:
        print(f"  FAIL  {path.name}")
        print(f"        {e}")
        return False

    print(f"  OK    {chip.name} ({chip.id})")
    print(f"        archetype: {chip.archetype} | voice: {chip.voice_signature}")
    print(f"        OCEAN: O={chip.openness} C={chip.conscientiousness} "
          f"E={chip.extraversion} A={chip.agreeableness} N={chip.neuroticism}")
    print(f"        EQ: awareness={chip.self_awareness} regulation={chip.self_regulation} "
          f"social={chip.social_awareness} empathy={chip.empathy_style}")
    print(f"        vulnerabilities: {len(chip.vulnerabilities)} | "
          f"strengths: {len(chip.strengths)} | anti-patterns: {len(chip.anti_patterns)}")
    print(f"        adaptive situations: {len(chip.adaptive)}")
    print(f"        mood: {chip.default_mood} | volatility: {chip.mood_volatility} | "
          f"carry-over: {chip.carry_over_weight}")

    # Show concise context preview
    print()
    print("    --- Context Preview (concise) ---")
    ctx = build_personality_context(chip, style="concise")
    for line in ctx.split("\n"):
        print(f"    {line}")

    # Show bridge payload summary
    print()
    print("    --- Bridge Payload Summary ---")
    payload = build_bridge_payload(chip)
    es = payload["emotional_state"]
    emotions_config = payload.get("personality_ext", {}).get("emotions_config", {})
    volatility = es.get("volatility", emotions_config.get("mood_volatility", "unknown"))
    print(f"    mood: {es['mood']} | intensity: {es['intensity']} | "
          f"volatility: {volatility}")
    hints = payload.get("guidance_hints", payload.get("guidance", {}))
    print(f"    pace: {hints['response_pace']} | tone: {hints['tone_shape']} | "
          f"verbosity: {hints['verbosity']}")

    print()
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_personality.py <file_or_directory>")
        sys.exit(1)

    if sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        sys.exit(0)

    target = Path(sys.argv[1])

    print()
    print("=" * 60)
    print("  Spark Personality Chip Validator")
    print(f"  Schema: spark-personality-chip.v1")
    print("=" * 60)
    print()

    if target.is_file():
        ok = validate_file(target)
        sys.exit(0 if ok else 1)

    elif target.is_dir():
        # Validate all chips in directory
        files = sorted(f for f in target.glob("*.personality.yaml") if not f.name.startswith("_"))
        dirs = [d for d in sorted(target.iterdir())
                if d.is_dir() and (d / "personality.yaml").exists()]

        total = len(files) + len(dirs)
        passed = 0

        if total == 0:
            print("  FAIL  no personality chips found")
            print("        Expected *.personality.yaml files or directories containing personality.yaml.")
            print("-" * 60)
            print("  Results: 0/0 passed")
            print("-" * 60)
            sys.exit(1)

        for f in files:
            if validate_file(f):
                passed += 1

        for d in dirs:
            if validate_file(d):
                passed += 1

        print("-" * 60)
        print(f"  Results: {passed}/{total} passed")
        print("-" * 60)
        sys.exit(0 if passed == total else 1)

    else:
        print(f"Not found: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
