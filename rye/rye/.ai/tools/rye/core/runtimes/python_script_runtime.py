# rye:validated:2026-02-04T04:59:28Z:8a346aca072319716e7fdd4b9d86ef8d5e8aaa7bbaeeb3850dda1a68221c7b8b
"""Python Runtime - Execute Python scripts.

Layer 2 runtime with __executor_id__ = "rye/core/primitives/subprocess".
Resolves Python interpreter via ENV_CONFIG before delegating.
"""

__version__ = "1.0.0"
__tool_type__ = "runtime"
__executor_id__ = "rye/core/primitives/subprocess"
__category__ = "rye/core/runtimes"
__tool_description__ = (
    "Python runtime executor - runs Python scripts with environment resolution"
)

ENV_CONFIG = {
    "interpreter": {
        "type": "venv_python",
        "venv_path": ".venv",
        "var": "RYE_PYTHON",
        "fallback": "python3",
    },
    "env": {
        "PYTHONUNBUFFERED": "1",
        "PROJECT_VENV_PYTHON": "${RYE_PYTHON}",
    },
}

CONFIG = {
    "command": "${RYE_PYTHON}",
    "args": [],
    "timeout": 300,
}

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "script": {
            "type": "string",
            "description": "Python script path or inline code",
        },
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Script arguments",
        },
        "module": {"type": "string", "description": "Module to run with -m flag"},
    },
}