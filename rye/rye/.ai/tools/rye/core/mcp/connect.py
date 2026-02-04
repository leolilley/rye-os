# rye:validated:2026-02-03T07:29:34Z:19f1b9207c863f8fc589757c3a0fa9b321b89dda061e8ef8d893ff6a790e345a
"""
MCP Call Tool

Executes a single tool call on an MCP server via Streamable HTTP transport.
Used by mcp_http_runtime to invoke MCP tools.

Usage:
    python mcp_call.py --url URL --tool TOOL_NAME --params '{"arg": "value"}' [--headers '{"KEY": "val"}']
"""

__tool_type__ = "python"
__version__ = "1.0.0"
__executor_id__ = "rye/core/runtimes/python_runtime"
__category__ = "rye/core/mcp"
__tool_description__ = (
    "MCP call tool - execute a single tool call on an MCP server via Streamable HTTP"
)

import json
import asyncio
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


async def execute(
    url: str,
    tool: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    **kwargs,
) -> Dict[str, Any]:
    """
    Execute a tool call on an MCP server.

    Args:
        url: MCP server URL (e.g., "https://mcp.context7.com/mcp")
        tool: Tool name to call (e.g., "resolve-library-id")
        params: Parameters to pass to the tool
        headers: HTTP headers (e.g., {"CONTEXT7_API_KEY": "..."})
        timeout: Request timeout in seconds

    Returns:
        Result dict with tool output or error
    """
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        import httpx

        logger.info(f"Calling MCP tool '{tool}' on {url}")

        # Create HTTP client with headers
        request_headers = dict(headers) if headers else {}
        http_client = httpx.AsyncClient(headers=request_headers, timeout=float(timeout))

        try:
            async with asyncio.timeout(timeout):
                async with streamable_http_client(url, http_client=http_client) as (
                    read,
                    write,
                    get_session_id,
                ):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        # Call the tool
                        result = await session.call_tool(tool, params or {})

                        # Extract content from result
                        if hasattr(result, "content") and result.content:
                            # MCP tool results have content array
                            content_items = []
                            for item in result.content:
                                if hasattr(item, "text"):
                                    content_items.append(
                                        {"type": "text", "text": item.text}
                                    )
                                elif hasattr(item, "data"):
                                    content_items.append(
                                        {"type": "data", "data": item.data}
                                    )
                                else:
                                    # Try to serialize the item
                                    if hasattr(item, "model_dump"):
                                        content_items.append(item.model_dump())
                                    else:
                                        content_items.append(str(item))

                            return {
                                "success": True,
                                "tool": tool,
                                "content": content_items,
                                "isError": getattr(result, "isError", False),
                            }
                        else:
                            return {
                                "success": True,
                                "tool": tool,
                                "content": [],
                                "raw": str(result),
                            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Timeout after {timeout} seconds",
                "tool": tool,
                "url": url,
            }

        finally:
            await http_client.aclose()

    except ImportError as e:
        return {
            "success": False,
            "error": f"MCP SDK not available: {e}",
            "solution": "Install MCP SDK: pip install mcp",
        }

    except Exception as e:
        logger.exception(f"Error calling MCP tool: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "tool": tool,
            "url": url,
        }


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="MCP Call Tool")
    parser.add_argument("--url", required=True, help="MCP server URL")
    parser.add_argument("--tool", required=True, help="Tool name to call")
    parser.add_argument("--params", default="{}", help="Tool parameters (JSON)")
    parser.add_argument("--headers", default="{}", help="HTTP headers (JSON)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    parser.add_argument(
        "--project-path",
        "--project_path",
        dest="project_path",
        help="Project path (ignored)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    result = asyncio.run(
        execute(
            url=args.url,
            tool=args.tool,
            params=json.loads(args.params),
            headers=json.loads(args.headers),
            timeout=args.timeout,
        )
    )

    print(json.dumps(result, indent=2), flush=True)
    sys.exit(0 if result.get("success") else 1)
