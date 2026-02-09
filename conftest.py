"""Pytest configuration for rye-os tests."""

import sys
from pathlib import Path

# Ensure the installed rye package takes precedence over tests/rye directory
# by removing tests directory from path if present
tests_dir = str(Path(__file__).parent / "tests")
if tests_dir in sys.path:
    sys.path.remove(tests_dir)
