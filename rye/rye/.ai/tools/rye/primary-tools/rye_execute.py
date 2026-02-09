"""Execute a directive, tool, or knowledge item via rye."""

import argparse
import json
import sys
import asyncio
from pathlib import Path

__version__ = "1.0.0"
__tool_type__ = "python"
__executor_id__ = "rye/core/runtimes/python_runtime"
__category__ = "rye/primary-tools"
__tool_description__ = "Execute a directive, tool, or knowledge item"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "item_type": {
            "type": "string",
            "enum": ["directive", "tool", "knowledge"],
            "description": "Type of item to execute",
        },
        "item_id": {
            "type": "string",
            "description": "ID of the item to execute (relative path without extension)",
        },
        "parameters": {
            "type": "object",
            "description": "Parameters to pass to the item",
            "default": {},
        },
        "dry_run": {
            "type": "boolean",
            "description": "Validate without executing",
            "default": False,
        },
    },
    "required": ["item_type", "item_id"],
}


def execute(params: dict, project_path: str) -> dict:
    try:
        from rye.tools.execute import ExecuteTool

        tool = ExecuteTool(project_path=project_path)
        result = asyncio.run(tool.handle(
            item_type=params["item_type"],
            item_id=params["item_id"],
            project_path=project_path,
            parameters=params.get("parameters", {}),
            dry_run=params.get("dry_run", False),
        ))
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", required=True)
    parser.add_argument("--project-path", required=True)
    args = parser.parse_args()
    result = execute(json.loads(args.params), args.project_path)
    print(json.dumps(result))
