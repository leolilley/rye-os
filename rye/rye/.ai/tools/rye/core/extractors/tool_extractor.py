# rye:validated:2026-02-02T00:00:00Z:placeholder
"""
Tool Extractor

Extracts metadata from tool files (.py, .yaml, .json, etc).
Handles Python tools with metadata in comments.
"""

__version__ = "1.0.0"
__tool_type__ = "extractor"
__executor_id__ = None
__category__ = "extractors"

# File extensions this extractor handles
EXTENSIONS = [".py", ".yaml", ".yml", ".json", ".js", ".sh", ".toml"]

# Parser type
PARSER = "python_ast"

# Signature format - line comment with # prefix
SIGNATURE_FORMAT = {
    "prefix": "#",
    "after_shebang": True,
}

# Extraction rules using path-based access (parsed data is a dict)
# For Python files, parser extracts module-level variables
EXTRACTION_RULES = {
    "name": {"type": "filename"},
    "version": {"type": "path", "key": "__version__"},
    "category": {"type": "path", "key": "__category__"},
    "description": {"type": "path", "key": "__docstring__"},
    "tool_type": {"type": "path", "key": "__tool_type__"},
    "executor_id": {"type": "path", "key": "__executor_id__"},
}

# Validation schema - tools have minimal required fields
# Name is derived from filename, category is optional in metadata
VALIDATION_SCHEMA = {
    "fields": {
        "name": {
            "required": True,
            "type": "string",
            "match_filename": True,
        },
        "category": {
            "required": False,
            "type": "string",
            "match_path": True,
        },
    },
}

