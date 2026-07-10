"""Verify spark_hook narrows exception handling to avoid swallowing KeyboardInterrupt."""
import pytest
from personality_engine.spark_hook import main


def test_spark_hook_module_loads():
    """Structural smoke — verifies spark_hook module imports after fix."""
    assert main is not None


def test_spark_hook_no_longer_catches_keyboard_interrupt():
    """Verify the except clause does not catch KeyboardInterrupt or SystemExit."""
    import inspect
    src = inspect.getsource(main)
    # The main() except block must not use bare Exception
    assert "except Exception" not in src, (
        "main() still uses broad except Exception — must narrow to "
        "(ValueError, json.JSONDecodeError, OSError) to preserve Ctrl+C"
    )
    # Confirm the narrow exception types are present
    assert "except (ValueError, json.JSONDecodeError, OSError) as exc:" in src
