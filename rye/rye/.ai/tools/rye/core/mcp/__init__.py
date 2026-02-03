# rye:validated:2026-02-03T01:19:05+00:00:2753291ba14fc506a285a8b591619b947a659516c59afb14cc1508e822712f00
"""MCP - connect to any MCP server."""

from .connect import execute as call_mcp_tool
from .discover import execute as discover_mcp_tools

__all__ = ["call_mcp_tool", "discover_mcp_tools"]
