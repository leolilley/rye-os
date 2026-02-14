"""Pytest configuration for rye-os tests."""

import sys
from pathlib import Path

# Ensure the installed rye package takes precedence over tests/rye directory
# by removing tests directory from path if present
tests_dir = str(Path(__file__).parent / "tests")
if tests_dir in sys.path:
    sys.path.remove(tests_dir)

# Runtime lib paths — mirrors what the anchor system injects via PYTHONPATH
# at execution time. Tests that load tool modules via importlib need these.
_runtime_lib = str(Path(__file__).parent / "rye" / "rye" / ".ai" / "tools" / "rye" / "core" / "runtimes" / "lib" / "python")
if _runtime_lib not in sys.path:
    sys.path.insert(0, _runtime_lib)
