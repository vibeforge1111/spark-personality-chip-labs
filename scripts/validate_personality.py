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


def validate_file(path: Path, *, verbose: bool = False, emit=None) -> bool:
    """Validate a single personality chip and print summary."""
    try:
        chip = load_personality(path)
    except (ValueError, FileNotFoundError) as e:
        line = f"  FAIL  {path.name}\n        {e}"
        if emit:
            emit(line)
        else:
            print(line)
        return False

    lines = [
        f"  OK    {chip.name} ({chip.id})",
        f"        archetype: {chip.archetype} | voice: {chip.voice_signature}",
        f"        OCEAN: O={chip.openness} C={chip.conscientiousness} "
        f"E={chip.extraversion} A={chip.agreeableness} N={chip.neuroticism}",
        f"        EQ: awareness={chip.self_awareness} regulation={chip.self_regulation} "
        f"social={chip.social_awareness} empathy={chip.empathy_style}",
        f"        vulnerabilities: {len(chip.vulnerabilities)} | "
        f"strengths: {len(chip.strengths)} | anti-patterns: {len(chip.anti_patterns)}",
        f"        adaptive situations: {len(chip.adaptive)}",
        f"        mood: {chip.default_mood} | volatility: {chip.mood_volatility} | "
        f"carry-over: {chip.carry_over_weight}",
    ]

    if verbose:
        lines.append("")
        lines.append("    --- Context Preview (concise) ---")
        ctx = build_personality_context(chip, style="concise")
        for line in ctx.split("\n"):
            lines.append(f"    {line}")

        lines.append("")
        lines.append("    --- Bridge Payload Summary ---")
        payload = build_bridge_payload(chip)
        es = payload["emotional_state"]
        emotions_config = payload.get("personality_ext", {}).get("emotions_config", {})
        volatility = es.get("volatility", emotions_config.get("mood_volatility", "unknown"))
        lines.append(f"    mood: {es['mood']} | intensity: {es['intensity']} | "
                     f"volatility: {volatility}")
        hints = payload.get("guidance_hints", payload.get("guidance", {}))
        lines.append(f"    pace: {hints['response_pace']} | tone: {hints['tone_shape']} | "
                     f"verbosity: {hints['verbosity']}")

    lines.append("")

    output = "\n".join(lines)
    if emit:
        emit(output)
    else:
        print(output)

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate a personality chip YAML file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("target", nargs="?", help="Personality file or directory to validate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output for each validation step")
    parser.add_argument("--output", type=str, default=None, help="Write output to file instead of stdout")

    args = parser.parse_args()

    if not args.target:
        parser.print_help()
        sys.exit(1)

    target = Path(args.target)

    lines = []
    def emit(line: str = ""):
        lines.append(line)
        if not args.output:
            print(line)

    emit()
    emit("=" * 60)
    emit("  Spark Personality Chip Validator")
    emit(f"  Schema: spark-personality-chip.v1")
    emit("=" * 60)
    emit()

    if target.is_file():
        ok = validate_file(target, verbose=args.verbose, emit=emit)
        if args.output:
            Path(args.output).write_text("\n".join(lines))
        sys.exit(0 if ok else 1)

    elif target.is_dir():
        # Validate all chips in directory
        files = sorted(f for f in target.glob("*.personality.yaml") if not f.name.startswith("_"))
        dirs = [d for d in sorted(target.iterdir())
                if d.is_dir() and (d / "personality.yaml").exists()]

        total = len(files) + len(dirs)
        passed = 0

        if total == 0:
            emit("  FAIL  no personality chips found")
            emit("        Expected *.personality.yaml files or directories containing personality.yaml.")
            emit("-" * 60)
            emit("  Results: 0/0 passed")
            emit("-" * 60)
            if args.output:
                Path(args.output).write_text("\n".join(lines))
            sys.exit(1)

        for f in files:
            if validate_file(f, verbose=args.verbose, emit=emit):
                passed += 1

        for d in dirs:
            if validate_file(d, verbose=args.verbose, emit=emit):
                passed += 1

        emit("-" * 60)
        emit(f"  Results: {passed}/{total} passed")
        emit("-" * 60)

        if args.output:
            Path(args.output).write_text("\n".join(lines))

        sys.exit(0 if passed == total else 1)

    else:
        emit(f"Not found: {target}")
        if args.output:
            Path(args.output).write_text("\n".join(lines))
        sys.exit(1)


if __name__ == "__main__":
    main()
