# kiwi-mcp:validated:2026-02-02T00:00:00Z:placeholder
"""HTTP Client Primitive - Execute HTTP requests.

Layer 1 primitive with __executor_id__ = None.
Routes directly to Lilux http_client primitive.
"""

__version__ = "1.0.0"
__tool_type__ = "primitive"
__executor_id__ = None
__category__ = "primitives"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"], "default": "GET"},
        "url": {"type": "string", "description": "Request URL (supports ${VAR} templating)"},
        "headers": {"type": "object", "description": "Request headers"},
        "body": {"type": "object", "description": "Request body (for POST/PUT/PATCH)"},
        "timeout": {"type": "integer", "default": 30, "description": "Timeout in seconds"},
        "auth": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["bearer", "api_key"]},
                "token": {"type": "string", "description": "Bearer token (supports ${VAR})"},
                "key": {"type": "string", "description": "API key (supports ${VAR})"},
                "header": {"type": "string", "default": "X-API-Key"},
            },
        },
        "retry": {
            "type": "object",
            "properties": {
                "max_attempts": {"type": "integer", "default": 1},
                "backoff": {"type": "string", "enum": ["exponential", "linear"], "default": "exponential"},
            },
        },
    },
    "required": ["url"],
}
