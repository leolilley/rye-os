# kiwi-mcp:validated:2026-02-02T00:00:00Z:placeholder
"""Python Runtime - Execute Python scripts.

Layer 2 runtime with __executor_id__ = "subprocess".
Resolves Python interpreter via ENV_CONFIG before delegating.
"""

__version__ = "1.0.0"
__tool_type__ = "runtime"
__executor_id__ = "subprocess"
__category__ = "runtimes"

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
        "script": {"type": "string", "description": "Python script path or inline code"},
        "args": {"type": "array", "items": {"type": "string"}, "description": "Script arguments"},
        "module": {"type": "string", "description": "Module to run with -m flag"},
    },
}
