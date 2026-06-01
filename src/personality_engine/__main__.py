"""Entry point for python -m personality_engine.

Routes to hook handlers:
    python -m personality_engine hooks session_start
    python -m personality_engine hooks pre_tool_use
    python -m personality_engine hooks post_tool_use

Also supports direct hook invocation:
    python -m personality_engine.hooks session_start
"""

import sys


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python -m personality_engine hooks <hook_name>\n"
            "       python -m personality_engine.hooks <hook_name>\n"
            "\n"
            "Available hooks: session_start, pre_tool_use, post_tool_use",
            file=sys.stderr,
        )
        sys.exit(1)

    subcommand = sys.argv[1]

    if subcommand == "hooks":
        # Shift argv so hooks.main() sees the hook name as argv[1]
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        from .hooks import main as hooks_main
        hooks_main()
    else:
        print(
            f"Unknown subcommand: {subcommand!r}. Known subcommands: hooks",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
