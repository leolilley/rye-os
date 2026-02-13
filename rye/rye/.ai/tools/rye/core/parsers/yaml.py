# rye:signed:2026-02-12T23:55:37Z:1809b1141acdcc8a3cde3d5b62427bd127b1b9aaf1e041503d4269127972625f:KpCvvt5P6auoCKTR7aCNgNa3pqjSHsdoWVD_TP3N0hFST511k6sNbfYXeDDNXJcqvaemDaKuR7EKfBeBOp1cBw==:440443d0858f0199
"""YAML parser for RYE."""

__version__ = "1.0.0"
__tool_type__ = "parser"
__category__ = "rye/core/parsers"
__tool_description__ = "YAML parser - parse YAML content into Python dictionaries"

import yaml


def parse(content):
    """Parse YAML content."""
    try:
        return {"data": yaml.safe_load(content) or {}, "content": content}
    except Exception:
        return {"data": {}, "content": content}
