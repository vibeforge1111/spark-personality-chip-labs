"""Claude Code hook handlers for personality chip injection.

Implements hook handlers for SessionStart, PreToolUse, and PostToolUse
that inject personality context into Claude Code agent workflows.

Usage:
    python -m personality_engine.hooks session_start   # inject personality at session start
    python -m personality_engine.hooks pre_tool_use    # adaptive personality for user state
    python -m personality_engine.hooks post_tool_use   # drift detection on tool output

Each handler reads JSON from stdin (Claude Code hook protocol) and writes
JSON to stdout with hookSpecificOutput for context injection.

v2: Uses room_reader for multi-signal user state detection,
    emotional_state for PAD-based dynamic emotions,
    ib_connector for Intelligence Builder sync.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Environment variable to disable personality hooks
DISABLE_ENV = "PERSONALITY_HOOKS_DISABLED"

# Commands that never need personality context
_SKIP_COMMANDS = frozenset({
    "git", "gh", "svn",
    "npm", "npx", "yarn", "pnpm", "bun", "pip", "pip3", "pipx",
    "poetry", "uv", "cargo", "go", "gem", "composer",
    "apt", "apt-get", "brew", "choco", "winget", "scoop",
    "ls", "dir", "cd", "pwd", "tree", "find", "which", "where",
    "wc", "du", "df", "stat", "file", "type",
    "cat", "head", "tail", "less", "more", "grep", "rg", "ag",
    "sort", "uniq", "diff",
    "ps", "top", "htop", "kill", "tasklist", "taskkill",
    "echo", "printf", "env", "set", "export", "printenv",
    "whoami", "hostname", "uname",
    "curl", "wget", "ping", "ssh", "scp", "rsync",
    "docker", "docker-compose", "kubectl",
    "make", "cmake", "tsc", "eslint", "prettier", "black",
    "ruff", "mypy", "pytest", "jest", "vitest",
    "bash", "sh", "zsh", "powershell", "cmd",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_stdin() -> dict[str, Any]:
    """Read JSON from stdin (Claude Code hook protocol)."""
    try:
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _write_stdout(data: dict[str, Any]) -> None:
    """Write JSON to stdout."""
    sys.stdout.write(json.dumps(data))
    sys.stdout.flush()


def _is_disabled() -> bool:
    """Check if personality hooks are disabled."""
    return os.environ.get(DISABLE_ENV, "").lower() in ("1", "true", "yes")


def _should_skip_command(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Fast pre-filter: return True if this tool action never needs personality."""
    if tool_name == "Bash":
        command = tool_input.get("command", "").strip()
        if not command:
            return True
        # Strip leading env var assignments (e.g., NODE_ENV=production npm install)
        tokens = command.split()
        first_token = tokens[0]
        while "=" in first_token and "/" not in first_token and "\" not in first_token:
            tokens = tokens[1:]
            if not tokens:
                return True
            first_token = tokens[0]
        base = first_token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        for suffix in (".exe", ".cmd", ".bat", ".ps1"):
            if base.lower().endswith(suffix):
                base = base[: -len(suffix)]
                break
        if base.lower() in _SKIP_COMMANDS:
            return True
    return False


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def handle_session_start(input_data: dict[str, Any]) -> dict[str, Any]:
    """SessionStart hook: inject personality context into the session.

    1. Resolve active personality (env var / active file / project dotfile)
    2. Write consciousness bridge file (with dynamic emotional state)
    3. Sync personality to Intelligence Builder's PersonalityEvolver
    4. Build concise + guardrails context
    5. Return via additionalContext
    """
    if _is_disabled():
        return {}

    try:
        from .active import get_active_personality
        from .context import build_personality_context
        from .bridge import write_bridge
    except ImportError:
        return {}

    cwd = input_data.get("cwd", "")
    chip = get_active_personality(project_dir=cwd)
    if not chip:
        return {}

    session_id = f"claude-code-{os.getpid()}"

    # Write the consciousness bridge for Spark Consciousness to read
    try:
        write_bridge(chip, session_id=session_id)
    except (ImportError, OSError) as exc:
        sys.stderr.write(f"bridge write failed: {exc}\n")  # non-blocking

    # Sync personality traits to Intelligence Builder's PersonalityEvolver
    try:
        from .ib_connector import sync_to_intelligence_builder
        sync_to_intelligence_builder(chip)
    except (ImportError, OSError) as exc:
        sys.stderr.write(f"IB sync failed: {exc}\n")  # non-blocking

    # Reset emotional state for fresh session
    try:
        from .emotional_state import reset_emotional_state
        reset_emotional_state()
    except (ImportError, OSError, ValueError) as exc:
        sys.stderr.write(f"emotional reset failed: {exc}\n")

    # Build personality context for the agent
    concise = build_personality_context(chip, style="concise")
    guardrails = build_personality_context(chip, style="guardrails")

    context = f"## Active Personality: {chip.name}\n\n{concise}"
    if guardrails:
        context += f"\n\n{guardrails}"

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


def handle_pre_tool_use(input_data: dict[str, Any]) -> dict[str, Any]:
    """PreToolUse hook: inject adaptive personality context if user state detected.

    Uses room_reader for multi-signal emotional detection across 9 states
    (frustrated, confused, excited, vulnerable, defensive, exhausted,
    curious, expert, rushed) with confidence scoring and trajectory tracking.

    Skips tools that don't need personality (git, npm, ls, etc.).
    """
    if _is_disabled():
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Only inject for tools where personality affects output
    if tool_name not in ("Bash", "Edit", "Write"):
        return {}

    if _should_skip_command(tool_name, tool_input):
        return {}

    try:
        from .active import get_active_personality
        from .context import build_personality_context
        from .room_reader import read_room_from_hook_input
    except ImportError:
        return {}

    chip = get_active_personality()
    if not chip:
        return {}

    # Multi-signal room reading (replaces old _detect_user_state)
    reading = read_room_from_hook_input(tool_input)
    if not reading.primary_state or reading.confidence < 0.25:
        return {}  # No confident state detected, skip injection

    user_state = reading.primary_state

    # Update emotional state based on room reading
    try:
        from .emotional_state import update_emotional_state
        update_emotional_state(chip, user_state=user_state, intensity=reading.confidence)
    except (ImportError, OSError, ValueError) as exc:
        sys.stderr.write(f"emotional update failed: {exc}\n")

    adaptive = build_personality_context(chip, style="adaptive", user_state=user_state)
    if not adaptive:
        return {}

    # Include trajectory info if available
    trajectory_note = ""
    if reading.trajectory != "stable":
        trajectory_note = f" [trajectory: {reading.trajectory}]"

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"[Personality adaptive: {user_state} "
                f"(confidence: {reading.confidence}){trajectory_note}]\n{adaptive}"
            ),
        }
    }


def handle_post_tool_use(input_data: dict[str, Any]) -> dict[str, Any]:
    """PostToolUse hook: run drift detection + emotional state update.

    1. Checks Bash/Edit/Write outputs for personality consistency
    2. Updates emotional state based on interaction context
    3. Logs drift signals to ~/.spark/chip_insights/personality_{id}.jsonl
    """
    if _is_disabled():
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_output = input_data.get("tool_output", "")

    if tool_name not in ("Bash", "Edit", "Write"):
        return {}

    if _should_skip_command(tool_name, tool_input):
        return {}

    # Only check text outputs of meaningful length
    if not isinstance(tool_output, str) or len(tool_output) < 50:
        return {}

    try:
        from .active import get_active_personality
        from .observer import observe_response
    except ImportError:
        return {}

    chip = get_active_personality()
    if not chip:
        return {}

    # Read the room from tool output (e.g., error messages indicate frustration context)
    try:
        from .room_reader import read_room
        from .emotional_state import update_emotional_state
        reading = read_room(tool_output[:1000])
        if reading.primary_state:
            update_emotional_state(
                chip,
                user_state=reading.primary_state,
                intensity=reading.confidence * 0.5,  # Dampen — output signals are indirect
            )
    except (ImportError, OSError, ValueError) as exc:
        sys.stderr.write(f"room read failed: {exc}\n")

    session_id = f"claude-code-{os.getpid()}"
    report = observe_response(
        chip,
        tool_output[:2000],  # Cap analysis length
        session_id=session_id,
    )

    # Only surface to agent if meaningful drift detected
    if report["drift_score"] >= 0.3:
        detail = f"Drift: {report['drift_score']} ({len(report['signals'])} signals)"
        if report.get("recommendation"):
            detail += f" - {report['recommendation']}"
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[Personality drift detected] {detail}",
            }
        }

    return {}


# ---------------------------------------------------------------------------
# Legacy compatibility — kept for existing tests
# ---------------------------------------------------------------------------

_STATE_SIGNALS = {
    "frustrated": [
        "not working", "broken", "still failing", "keeps failing",
        "doesn't work", "can't figure", "tried everything",
        "this is wrong", "error again",
    ],
    "stuck": [
        "stuck", "blocked", "don't know how", "no idea",
        "help me", "confused", "lost",
    ],
    "expert": [
        "i know", "obviously", "clearly", "just need",
        "simple fix", "skip the explanation",
    ],
    "deadline_pressure": [
        "asap", "urgent", "deadline", "hurry", "quickly",
        "right now", "immediately", "time sensitive",
    ],
}


def _detect_user_state(tool_input: dict[str, Any]) -> str | None:
    """Legacy user state detection — kept for backwards compatibility.

    New code should use room_reader.read_room_from_hook_input() instead.
    """
    text_parts = []
    if "command" in tool_input:
        text_parts.append(tool_input["command"])
    if "description" in tool_input:
        text_parts.append(tool_input["description"])

    if not text_parts:
        return None

    text_lower = " ".join(text_parts).lower()

    for state, signals in _STATE_SIGNALS.items():
        for signal in signals:
            if signal in text_lower:
                return state

    return None


# ---------------------------------------------------------------------------
# CLI dispatcher
# ---------------------------------------------------------------------------

HANDLERS = {
    "session_start": handle_session_start,
    "pre_tool_use": handle_pre_tool_use,
    "post_tool_use": handle_post_tool_use,
}


def main() -> None:
    """CLI entry point: dispatch to the appropriate hook handler."""
    if len(sys.argv) < 2:
        print(
            json.dumps({"error": "Usage: python -m personality_engine.hooks <hook_name>"}),
            file=sys.stderr,
        )
        sys.exit(1)

    hook_name = sys.argv[1]
    handler = HANDLERS.get(hook_name)

    if handler is None:
        print(
            json.dumps({"error": f"Unknown hook: {hook_name}. Available: {list(HANDLERS.keys())}"}),
            file=sys.stderr,
        )
        sys.exit(1)

    input_data = _read_stdin()
    result = handler(input_data)

    if result:
        _write_stdout(result)


if __name__ == "__main__":
    main()
