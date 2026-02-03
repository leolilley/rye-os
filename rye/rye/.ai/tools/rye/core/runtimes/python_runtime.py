# rye:validated:2026-02-03T07:29:34Z:6bf671b4c91149cf3ac10c49a472c0671cf93ee8a4fc28971105558c7f4baf99
"""Python Runtime - Execute Python scripts.

Layer 2 runtime with __executor_id__ = "subprocess".
Resolves Python interpreter via ENV_CONFIG before delegating.
"""

__version__ = "1.0.0"
__tool_type__ = "runtime"
__executor_id__ = "subprocess"
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
