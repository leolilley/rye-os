#!/usr/bin/env python3
"""Sign all updated tools and directives."""

import asyncio
import sys
from pathlib import Path

# Add rye to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rye"))

from rye.tools.sign import SignTool


async def main():
    """Sign all updated files."""
    # The rye package root (where .ai/ directory lives)
    rye_root = Path(__file__).parent.parent / "rye" / "rye"
    project_path = str(rye_root)

    tool = SignTool()

    # Tools to sign (just the filename without .py extension)
    # The sign tool searches recursively in the tools directory
    tools = [
        "system",
        "python_runtime",
        "node_runtime",
        "subprocess",
        "http_client",
        "directive_extractor",
        "knowledge_extractor",
        "tool_extractor",
        "null_sink",
        "file_sink",
        "websocket_sink",
        "discover",
        "connect",
        "mcp_logs",
        "jsonrpc_handler",
        "yaml",
        "python_ast",
        "markdown_xml",
        "markdown_frontmatter",
        "registry",
    ]

    print(f"Signing tools from: {project_path}/.ai/tools/")
    print("=" * 60)

    for tool_id in tools:
        try:
            result = await tool.handle(
                item_type="tool",
                item_id=tool_id,
                project_path=project_path,
                source="project",
            )
            if result["status"] == "signed":
                print(f"  ✓ {tool_id}")
            else:
                print(f"  ✗ {tool_id}: {result.get('error', 'Unknown error')}")
                if "issues" in result:
                    for issue in result["issues"]:
                        print(f"      - {issue}")
        except Exception as e:
            print(f"  ✗ {tool_id}: {e}")

    # Sign directives (just filename without .md extension)
    directives = [
        "create_directive",
        "create_advanced_directive",
    ]

    print("\nSigning directives...")
    print("=" * 60)

    for directive_id in directives:
        try:
            result = await tool.handle(
                item_type="directive",
                item_id=directive_id,
                project_path=project_path,
                source="project",
            )
            if result["status"] == "signed":
                print(f"  ✓ {directive_id}")
            else:
                print(f"  ✗ {directive_id}: {result.get('error', 'Unknown error')}")
                if "issues" in result:
                    for issue in result["issues"]:
                        print(f"      - {issue}")
        except Exception as e:
            print(f"  ✗ {directive_id}: {e}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
