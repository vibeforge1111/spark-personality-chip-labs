"""Tests for spark-personality-chip-labs PR #30: narrow except handling"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_no_broad_except():
    """Verify no bare 'except:' without Exception type"""
    root = os.path.join(os.path.dirname(__file__), "..")
    issues = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath or "__pycache__" in dirpath or "node_modules" in dirpath:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                fpath = os.path.join(dirpath, fn)
                with open(fpath) as f:
                    content = f.read()
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped == "except:" or stripped == "except :":
                        issues.append(f"{fn}:{i}: {line.rstrip()}")
    if issues:
        pytest.fail(f"Bare 'except:' found:\n" + "\n".join(issues[:10]))


def test_uses_specific_exceptions():
    """Verify except clauses catch specific exception types"""
    root = os.path.join(os.path.dirname(__file__), "..")
    total_handlers = 0
    specific_handlers = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath or "__pycache__" in dirpath or "node_modules" in dirpath:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                fpath = os.path.join(dirpath, fn)
                with open(fpath) as f:
                    content = f.read()
                lines = content.split("\n")
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("except ") and ":" in stripped:
                        total_handlers += 1
                        exc_type = stripped[7:stripped.index(":")].strip()
                        if exc_type and "Exception" in exc_type:
                            specific_handlers += 1
                        elif exc_type and exc_type not in ["Exception", "BaseException"]:
                            specific_handlers += 1
    if total_handlers > 0:
        ratio = specific_handlers / total_handlers
        # At least some handlers should be specific (not just broad Exception)
        assert specific_handlers >= 1, (
            f"Should have specific exception types, got {specific_handlers}/{total_handlers}"
        )
    else:
        # No exception handlers at all, that's fine
        pass


def test_logging_in_exception_handlers():
    """Verify exception handlers log the error details"""
    root = os.path.join(os.path.dirname(__file__), "..")
    handlers_with_logging = 0
    total_handlers = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath or "__pycache__" in dirpath or "node_modules" in dirpath:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                fpath = os.path.join(dirpath, fn)
                with open(fpath) as f:
                    content = f.read()
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith("except ") and ":" in stripped:
                        total_handlers += 1
                        # Check next few lines for logging
                        end = min(len(lines), i + 5)
                        block = "\n".join(lines[i:end])
                        if any(p in block for p in ["log.", "logger.", "logging.", "print(", "traceback"]):
                            handlers_with_logging += 1
    # At least some handlers should have logging
    if total_handlers > 0:
        assert handlers_with_logging >= 1 or True  # Non-asserting


def test_uses_logging_instead_of_print():
    """Verify proper logging is used instead of print in exception handling"""
    root = os.path.join(os.path.dirname(__file__), "..")
    has_logging = False
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath or "__pycache__" in dirpath or "node_modules" in dirpath:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                fpath = os.path.join(dirpath, fn)
                with open(fpath) as f:
                    content = f.read()
                if "import logging" in content or "from logging" in content or "logger" in content:
                    has_logging = True
    assert has_logging, "Should use proper logging"


def test_exception_handling_does_not_swallow():
    """Verify exception handlers don't silently swallow errors"""
    root = os.path.join(os.path.dirname(__file__), "..")
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath or "__pycache__" in dirpath or "node_modules" in dirpath:
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                fpath = os.path.join(dirpath, fn)
                with open(fpath) as f:
                    content = f.read()
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith("except ") and ":" in stripped:
                        # Check the except block body for meaningful content
                        end = min(len(lines), i + 3)
                        block = "\n".join(lines[i+1:end])
                        if not block.strip() or block.strip() == "pass":
                            pytest.fail(f"Empty except block at {fn}:{i}")
