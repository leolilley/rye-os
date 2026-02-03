# rye:validated:2026-02-03T07:29:34Z:fd2325b4c3ee52951878d1194a9e2cd08d7d9178b53f29d1e9aa77851a49d7ba
"""Subprocess Primitive - Execute shell commands.

Layer 1 primitive with __executor_id__ = None.
Routes directly to Lilux subprocess primitive.
"""

__version__ = "1.0.0"
__tool_type__ = "primitive"
__executor_id__ = None
__category__ = "rye/core/primitives"
__tool_description__ = (
    "Subprocess primitive - execute shell commands with configurable arguments"
)

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Command to execute"},
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Command arguments",
        },
        "cwd": {"type": "string", "description": "Working directory"},
        "env": {"type": "object", "description": "Environment variables"},
        "timeout": {
            "type": "integer",
            "default": 300,
            "description": "Timeout in seconds",
        },
        "input_data": {"type": "string", "description": "Data to pipe to stdin"},
    },
    "required": ["command"],
}
