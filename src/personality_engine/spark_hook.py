from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .active import get_active_personality, get_active_personality_id
from .ib_connector import build_builder_personality_import

MAX_HOOK_INPUT_BYTES = 1_000_000


def handle_personality_hook(payload: dict[str, Any]) -> dict[str, Any]:
    human_id = str(payload.get("human_id") or "").strip()
    agent_id = str(payload.get("agent_id") or "").strip()
    if not human_id or not agent_id:
        raise ValueError("personality hook requires human_id and agent_id.")

    project_dir = str(Path.cwd())
    chip = get_active_personality(project_dir=project_dir)
    if chip is None:
        configured_id = get_active_personality_id(project_dir=project_dir)
        if configured_id:
            raise ValueError(
                f"Active personality id {configured_id!r} is configured but no matching "
                "personality chip file was found. Check ~/.spark/chips/personality/ or "
                "the repo personalities/ directory for "
                f"{configured_id}.personality.yaml (or {configured_id}/personality.yaml)."
            )
        raise ValueError(
            "No active personality chip is configured. Set SPARK_PERSONALITY, "
            "write ~/.spark/active_personality.json, or add a project .personality file."
        )

    result = build_builder_personality_import(
        chip,
        human_id=human_id,
        agent_id=agent_id,
        evolver_state_path=payload.get("evolver_state_path"),
    )
    return {
        "returncode": 0,
        "stdout": (
            f"personality_id: {result['personality_id']}\n"
            f"persona_name: {result['persona_name']}\n"
            f"behavioral_rules: {len(result['behavioral_rules'])}"
        ),
        "stderr": "",
        "metrics": {
            "behavioral_rule_count": len(result["behavioral_rules"]),
            "trait_count": len(result["base_traits"]),
        },
        "result": result,
    }


def _write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_hook_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError("Spark hook input file not found.")
    if path.stat().st_size > MAX_HOOK_INPUT_BYTES:
        raise ValueError("Spark hook input payload is too large.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Spark hook input at {path} contains invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Spark hook input payload must be a JSON object.")
    return payload


def _error_output(message: str) -> dict[str, Any]:
    return {
        "returncode": 1,
        "stdout": "",
        "stderr": message,
        "metrics": {},
        "result": {},
        "error": message,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("hook", choices=["personality"])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        payload = _read_hook_payload(input_path)
        if args.hook != "personality":
            raise ValueError(f"Unsupported hook: {args.hook!r}. Supported hooks: 'personality'.")
        result = handle_personality_hook(payload)
    except Exception as exc:
        _write_output(output_path, _error_output(str(exc)))
        return 1

    _write_output(output_path, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
