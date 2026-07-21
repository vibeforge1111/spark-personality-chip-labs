"""Tests for Claude Code personality hooks."""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from personality_engine.hooks import (
    handle_session_start,
    handle_pre_tool_use,
    handle_post_tool_use,
    _should_skip_command,
    _detect_user_state,
)
from personality_engine.active import clear_cache
from personality_engine.schema import SCHEMA_VERSION, build_personality


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment between tests."""
    clear_cache()
    os.environ.pop("PERSONALITY_HOOKS_DISABLED", None)
    os.environ.pop("SPARK_PERSONALITY", None)
    yield
    clear_cache()
    os.environ.pop("PERSONALITY_HOOKS_DISABLED", None)
    os.environ.pop("SPARK_PERSONALITY", None)


@pytest.fixture
def personality_dir(tmp_path):
    """Create a temp directory with a test personality."""
    import yaml

    chip_data = {
        "schema": SCHEMA_VERSION,
        "identity": {
            "id": "hook-test",
            "name": "HookTest",
            "archetype": "builder",
            "voice_signature": "direct and clear",
        },
        "traits": {"openness": 0.70, "conscientiousness": 0.80},
        "preferences": {
            "communication": {"verbosity": "moderate", "formality": "professional"},
        },
        "anti_patterns": ["Never dismiss user concerns"],
        "adaptive": {
            "when_user_frustrated": {
                "tone_shift": "warmer",
                "strategy": "acknowledge first",
            },
        },
    }

    chip_file = tmp_path / "hook-test.personality.yaml"
    with open(chip_file, "w", encoding="utf-8") as f:
        yaml.dump(chip_data, f)

    return tmp_path


class TestSkipCommand:

    def test_skip_git(self):
        assert _should_skip_command("Bash", {"command": "git status"}) is True

    def test_skip_npm(self):
        assert _should_skip_command("Bash", {"command": "npm install"}) is True

    def test_skip_ls(self):
        assert _should_skip_command("Bash", {"command": "ls -la"}) is True

    def test_skip_empty(self):
        assert _should_skip_command("Bash", {"command": ""}) is True

    def test_dont_skip_python(self):
        assert _should_skip_command("Bash", {"command": "python run.py"}) is False

    def test_dont_skip_edit(self):
        assert _should_skip_command("Edit", {"file_path": "src/main.py"}) is False

    def test_skip_windows_exe(self):
        assert _should_skip_command("Bash", {"command": "git.exe status"}) is True

    @pytest.mark.parametrize("command", [None, 1, [], {}])
    def test_skip_malformed_command_values(self, command):
        assert _should_skip_command("Bash", {"command": command}) is True

    def test_skip_env_prefixed_and_quoted_command(self):
        assert _should_skip_command("Bash", {"command": 'FOO=bar env BAZ=1 "/usr/bin/git" status'}) is True

    def test_chained_real_work_is_not_hidden_by_skipped_prefix(self):
        assert _should_skip_command("Bash", {"command": "cd /tmp && python app.py"}) is False
        assert _should_skip_command("Bash", {"command": "git status | python app.py"}) is False

    def test_all_skipped_chain_remains_skipped(self):
        assert _should_skip_command("Bash", {"command": "cd /tmp && git status; ls"}) is True


class TestDetectUserState:

    def test_frustrated(self):
        assert _detect_user_state({"command": "# still failing, tried everything"}) == "frustrated"

    def test_stuck(self):
        assert _detect_user_state({"description": "I'm stuck on this"}) == "stuck"

    def test_expert(self):
        assert _detect_user_state({"command": "# obviously just need to fix the import"}) == "expert"

    def test_deadline(self):
        assert _detect_user_state({"description": "This is urgent, asap"}) == "deadline_pressure"

    def test_no_state(self):
        assert _detect_user_state({"command": "python main.py"}) is None

    def test_empty_input(self):
        assert _detect_user_state({}) is None


class TestSessionStart:

    def test_disabled(self):
        os.environ["PERSONALITY_HOOKS_DISABLED"] = "1"
        result = handle_session_start({})
        assert result == {}

    def test_no_personality_active(self, tmp_path):
        with patch("personality_engine.hooks.os.environ", {"PERSONALITY_HOOKS_DISABLED": ""}):
            # No SPARK_PERSONALITY set, no active file
            with patch("personality_engine.active.ACTIVE_FILE", tmp_path / "nope.json"):
                result = handle_session_start({"cwd": str(tmp_path)})
                assert result == {}

    def test_with_active_personality(self, personality_dir):
        os.environ["SPARK_PERSONALITY"] = "hook-test"
        with patch("personality_engine.active.ACTIVE_FILE", personality_dir / "nope.json"):
            result = handle_session_start({"cwd": str(personality_dir)})

            # Calling with search_paths requires patching get_active_personality
            # Instead, test with explicit search_paths via the active module
            from personality_engine.active import get_active_personality
            chip = get_active_personality(search_paths=[personality_dir])
            assert chip is not None
            assert chip.id == "hook-test"

    def test_returns_context_structure(self, personality_dir):
        """Test that session_start returns correct hook protocol structure."""
        os.environ["SPARK_PERSONALITY"] = "hook-test"

        chip = build_personality({
            "identity": {"id": "hook-test", "name": "HookTest", "archetype": "builder"},
            "anti_patterns": ["Never dismiss user concerns"],
        })

        with patch("personality_engine.active.get_active_personality", return_value=chip):
            result = handle_session_start({"cwd": "/test"})

        assert "hookSpecificOutput" in result
        assert result["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "additionalContext" in result["hookSpecificOutput"]
        assert "HookTest" in result["hookSpecificOutput"]["additionalContext"]


class TestPreToolUse:

    def test_disabled(self):
        os.environ["PERSONALITY_HOOKS_DISABLED"] = "true"
        result = handle_pre_tool_use({"tool_name": "Bash"})
        assert result == {}

    def test_skips_non_bash_edit_write(self):
        result = handle_pre_tool_use({"tool_name": "Read", "tool_input": {}})
        assert result == {}

    def test_skips_git(self):
        result = handle_pre_tool_use({
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
        })
        assert result == {}

    def test_no_state_no_output(self):
        """If no user state detected, PreToolUse returns empty."""
        chip = build_personality({
            "identity": {"id": "test-pre", "name": "TestPre"},
        })
        with patch("personality_engine.active.get_active_personality", return_value=chip):
            result = handle_pre_tool_use({
                "tool_name": "Bash",
                "tool_input": {"command": "python main.py"},
            })
        assert result == {}

    def test_frustrated_state_returns_adaptive(self):
        """If frustrated state detected, returns adaptive context."""
        chip = build_personality({
            "identity": {"id": "test-pre", "name": "TestPre"},
            "adaptive": {
                "when_user_frustrated": {
                    "tone_shift": "warmer",
                    "strategy": "acknowledge first",
                },
            },
        })
        with patch("personality_engine.active.get_active_personality", return_value=chip):
            result = handle_pre_tool_use({
                "tool_name": "Bash",
                "tool_input": {"command": "# still failing tried everything"},
            })
        assert "hookSpecificOutput" in result
        assert "frustrated" in result["hookSpecificOutput"]["additionalContext"]

    def test_resolves_project_personality_for_pre_tool_hook(self):
        chip = build_personality({"identity": {"id": "project-pre", "name": "ProjectPre"}})
        with patch("personality_engine.active.get_active_personality", return_value=chip) as get_active:
            handle_pre_tool_use({
                "cwd": "/workspace/project",
                "tool_name": "Bash",
                "tool_input": {"command": "# still failing tried everything"},
            })

        get_active.assert_called_once_with(project_dir="/workspace/project")


class TestPostToolUse:

    def test_disabled(self):
        os.environ["PERSONALITY_HOOKS_DISABLED"] = "yes"
        result = handle_post_tool_use({"tool_name": "Bash"})
        assert result == {}

    def test_skips_read(self):
        result = handle_post_tool_use({"tool_name": "Read"})
        assert result == {}

    def test_skips_short_output(self):
        result = handle_post_tool_use({
            "tool_name": "Bash",
            "tool_input": {"command": "python x.py"},
            "tool_output": "ok",
        })
        assert result == {}

    def test_no_drift_no_output(self):
        """Clean output should not trigger drift notification."""
        chip = build_personality({
            "identity": {"id": "test-post", "name": "TestPost"},
        })
        with patch("personality_engine.active.get_active_personality", return_value=chip):
            result = handle_post_tool_use({
                "tool_name": "Bash",
                "tool_input": {"command": "python main.py"},
                "tool_output": "Here is the result of the analysis. " * 5,
            })
        assert result == {}

    def test_resolves_project_personality_for_post_tool_hook(self):
        chip = build_personality({"identity": {"id": "project-post", "name": "ProjectPost"}})
        with patch("personality_engine.active.get_active_personality", return_value=chip) as get_active:
            handle_post_tool_use({
                "cwd": "/workspace/project",
                "tool_name": "Bash",
                "tool_input": {"command": "python main.py"},
                "tool_output": "Here is the result of the analysis. " * 5,
            })

        get_active.assert_called_once_with(project_dir="/workspace/project")

    def test_agent_output_does_not_update_user_emotional_state(self):
        chip = build_personality({"identity": {"id": "post-owner", "name": "PostOwner"}})
        with (
            patch("personality_engine.active.get_active_personality", return_value=chip),
            patch("personality_engine.observer.observe_response", return_value={"drift_score": 0.0, "signals": []}),
            patch("personality_engine.room_reader.read_room") as read_room,
            patch("personality_engine.emotional_state.update_emotional_state") as update_state,
        ):
            result = handle_post_tool_use({
                "tool_name": "Bash",
                "tool_input": {"command": "python app.py"},
                "tool_output": "The user seems frustrated and exhausted. " * 4,
            })
        assert result == {}
        read_room.assert_not_called()
        update_state.assert_not_called()

    def test_observer_failure_is_nonreflecting_and_nonblocking(self, capsys):
        chip = build_personality({"identity": {"id": "post-owner", "name": "PostOwner"}})
        with (
            patch("personality_engine.active.get_active_personality", return_value=chip),
            patch("personality_engine.observer.observe_response", side_effect=ValueError("/secret/path")),
        ):
            result = handle_post_tool_use({
                "tool_name": "Bash",
                "tool_input": {"command": "python app.py"},
                "tool_output": "A sufficiently long agent response for observation. " * 3,
            })
        captured = capsys.readouterr()
        assert result == {}
        assert captured.err == "[spark-personality] drift observation failed: ValueError\n"
        assert "/secret/path" not in captured.err


def test_read_stdin_handles_unicode_decode_failure_without_reflection(capsys):
    from personality_engine.hooks import _read_stdin

    class BrokenInput:
        def read(self, _limit):
            raise UnicodeDecodeError("utf-8", b"secret", 0, 1, "private detail")

    with patch.object(sys, "stdin", BrokenInput()):
        assert _read_stdin() == {}
    captured = capsys.readouterr()
    assert captured.err == "[spark-personality] ignored invalid hook input: UnicodeDecodeError\n"
    assert "private detail" not in captured.err
