# rye:signed:2026-02-14T00:37:49Z:cfc22b8545a6389adf74b2195fab2aa6d0e1fa4976bde3a41d90f948a51f11b0:JXEILjOzgPZhIfswYs-7LBMNXOUO-s_FpPIbOrDFwjMauZc8VQJ27vE_ZgcyFu5Pg646ZltgNwe9SDAwri9HAQ==:440443d0858f0199
"""MCP tools package."""

__version__ = "1.0.0"
__tool_type__ = "python"
__category__ = "rye/mcp"
__tool_description__ = "MCP tools package"

from .connect import call_http, call_stdio, execute_with_server_config
from .discover import execute as discover_mcp_tools

__all__ = [
    "call_http",
    "call_stdio",
    "execute_with_server_config",
    "discover_mcp_tools",
]
