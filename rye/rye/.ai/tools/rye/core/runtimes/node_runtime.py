# kiwi-mcp:validated:2026-02-02T00:00:00Z:placeholder
"""Node.js Runtime - Execute JavaScript/TypeScript.

Layer 2 runtime with __executor_id__ = "subprocess".
Resolves Node interpreter via ENV_CONFIG before delegating.
"""

__version__ = "1.0.0"
__tool_type__ = "runtime"
__executor_id__ = "subprocess"
__category__ = "runtimes"

ENV_CONFIG = {
    "interpreter": {
        "type": "node_modules",
        "search_paths": ["node_modules/.bin"],
        "var": "RYE_NODE",
        "fallback": "node",
    },
    "env": {
        "NODE_ENV": "development",
    },
}

CONFIG = {
    "command": "${RYE_NODE}",
    "args": [],
    "timeout": 300,
}

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "script": {"type": "string", "description": "JavaScript file path"},
        "args": {"type": "array", "items": {"type": "string"}, "description": "Script arguments"},
    },
}
