#!/usr/bin/env python3
"""
Validate a personality chip YAML file.

Usage:
    python scripts/validate_personality.py personalities/artemis.personality.yaml
    python scripts/validate_personality.py personalities/  # validate all in directory
"""

import argparse
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from personality_engine.loader import load_personality, load_all_personalities
from personality_engine.context import build_personality_context
from personality_engine.bridge import build_bridge_payload


def validate_file(path: Path, *, verbose: bool = False) -> bool:
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

    if verbose:
        print()
        print("    --- Context Preview (concise) ---")
        ctx = build_personality_context(chip, style="concise")
        for line in ctx.split("\n"):
            print(f"    {line}")

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


def _run_validation(target: Path, *, verbose: bool) -> int:

    print()
    print("=" * 60)
    print("  Spark Personality Chip Validator")
    print(f"  Schema: spark-personality-chip.v1")
    print("=" * 60)
    print()

    if target.is_file():
        return 0 if validate_file(target, verbose=verbose) else 1

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
            return 1

        for f in files:
            if validate_file(f, verbose=verbose):
                passed += 1

        for d in dirs:
            if validate_file(d, verbose=verbose):
                passed += 1

        print("-" * 60)
        print(f"  Results: {passed}/{total} passed")
        print("-" * 60)
        return 0 if passed == total else 1

    else:
        print(f"Not found: {target}")
        return 1


def _write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a personality chip YAML file.")
    parser.add_argument("target", nargs="?", help="personality file or directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="include context and bridge details")
    parser.add_argument("--output", type=Path, help="write the report to a file instead of stdout")
    if len(sys.argv) > 1 and sys.argv[1].strip().lower() == "help":
        parser.print_help()
        return 0
    args = parser.parse_args()
    if not args.target:
        parser.print_help()
        return 1

    target = Path(args.target).expanduser()
    output = args.output.expanduser() if args.output else None
    if output and output.resolve(strict=False) == target.resolve(strict=False):
        parser.error("--output must not overwrite the validation target")

    if output:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = _run_validation(target, verbose=args.verbose)
        _write_output(output, buffer.getvalue())
        return code
    return _run_validation(target, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
