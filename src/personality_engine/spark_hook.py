from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .active import get_active_personality, get_active_personality_id
from .ib_connector import build_builder_personality_import

MAX_HOOK_INPUT_BYTES = 1_000_000


class HookInputError(ValueError):
    """Expected malformed hook input with a stable machine-readable code."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class HookConfigurationError(ValueError):
    """Expected active-personality configuration failure."""


def handle_personality_hook(payload: dict[str, Any]) -> dict[str, Any]:
    human_id = str(payload.get("human_id") or "").strip()
    agent_id = str(payload.get("agent_id") or "").strip()
    if not human_id or not agent_id:
        raise HookInputError(
            "personality hook requires human_id and agent_id.",
            "missing_identity",
        )

    project_dir = str(Path.cwd())
    chip = get_active_personality(project_dir=project_dir)
    if chip is None:
        configured_id = get_active_personality_id(project_dir=project_dir)
        if configured_id:
            raise HookConfigurationError(
                f"Active personality id {configured_id!r} is configured but no matching "
                "personality chip file was found. Check ~/.spark/chips/personality/ or "
                "the repo personalities/ directory for "
                f"{configured_id}.personality.yaml (or {configured_id}/personality.yaml)."
            )
        raise HookConfigurationError(
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
    from .storage import atomic_write_json
    atomic_write_json(path, payload)


def _read_hook_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise HookInputError("Spark hook input file not found.", "input_missing")
    if path.stat().st_size > MAX_HOOK_INPUT_BYTES:
        raise HookInputError("Spark hook input payload is too large.", "input_too_large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HookInputError(
            "Spark hook input contains invalid JSON.",
            "invalid_json",
        ) from exc
    if not isinstance(payload, dict):
        raise HookInputError(
            "Spark hook input payload must be a JSON object.",
            "input_not_object",
        )
    return payload


def _error_output(message: str, *, error_type: str, error_code: str) -> dict[str, Any]:
    return {
        "returncode": 1,
        "stdout": "",
        "stderr": message,
        "metrics": {},
        "result": {},
        "error": message,
        "error_type": error_type,
        "error_code": error_code,
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
    except HookInputError as exc:
        error = _error_output(
            str(exc), error_type="validation", error_code=exc.code,
        )
        _write_output(output_path, error)
        return 1
    except HookConfigurationError:
        error = _error_output(
            "Personality configuration is unavailable. Check the active "
            "personality selection and installed chip files.",
            error_type="configuration",
            error_code="personality_unavailable",
        )
        _write_output(output_path, error)
        return 1
    except ValueError:
        error = _error_output(
            "Personality hook request was rejected.",
            error_type="validation",
            error_code="request_rejected",
        )
        _write_output(output_path, error)
        return 1
    except OSError:
        error = _error_output(
            "Personality hook could not read or write its local state.",
            error_type="io",
            error_code="state_io_failed",
        )
        _write_output(output_path, error)
        return 1
    except Exception:
        error = _error_output(
            "An unexpected error occurred in the personality hook.",
            error_type="unexpected",
            error_code="unexpected_failure",
        )
        _write_output(output_path, error)
        return 1

    _write_output(output_path, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
