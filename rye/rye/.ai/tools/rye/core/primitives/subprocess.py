# kiwi-mcp:validated:2026-02-02T00:00:00Z:placeholder
"""Subprocess Primitive - Execute shell commands.

Layer 1 primitive with __executor_id__ = None.
Routes directly to Lilux subprocess primitive.
"""

__version__ = "1.0.0"
__tool_type__ = "primitive"
__executor_id__ = None
__category__ = "primitives"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Command to execute"},
        "args": {"type": "array", "items": {"type": "string"}, "description": "Command arguments"},
        "cwd": {"type": "string", "description": "Working directory"},
        "env": {"type": "object", "description": "Environment variables"},
        "timeout": {"type": "integer", "default": 300, "description": "Timeout in seconds"},
        "input_data": {"type": "string", "description": "Data to pipe to stdin"},
    },
    "required": ["command"],
}
