# rye:validated:2026-02-04T04:59:28Z:80530fce37446987cff605718508c14e305007c08ba3dc70cd0f8e263056f678
"""Python Tool Runtime - Execute Python tools with async execute().

Layer 2 runtime with __executor_id__ = "rye/core/primitives/subprocess".
Resolves Python interpreter via ENV_CONFIG before delegating to a runner
that imports the tool module and calls execute(action, project_path, params).

Use this runtime for Python tools that have an execute(action, project_path, params)
function. Use python_runtime for running Python scripts directly.
"""

__version__ = "1.0.0"
__tool_type__ = "runtime"
__executor_id__ = "rye/core/primitives/subprocess"
__category__ = "rye/core/runtimes"
__tool_description__ = "Python tool runtime - calls async execute() in tool modules"

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
    "args": [
        "-m", "rye.tool_runner",
        "{tool_path}",
        "--action", "{action}",
        "--params", "{params_json}",
        "--project-path", "{project_path}",
    ],
    "timeout": 300,
}

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "Action to execute on the tool",
        },
        "timeout": {
            "type": "number",
            "description": "Execution timeout in seconds",
        },
    },
    "required": ["action"],
}
