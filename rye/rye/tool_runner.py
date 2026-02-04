"""Tool runner - imports Python tool modules and calls their execute() function.

Invoked by python_tool_runtime via subprocess. This runner:
1. Derives the proper module name from tool_path (preserving relative imports)
2. Imports the tool module
3. Calls its async execute(action, project_path, params) function
4. Outputs JSON result to stdout

Usage:
    python -m rye.tool_runner <tool_path> --action <action> --params <json> --project-path <path>
"""

import argparse
import asyncio
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def module_name_from_tool_path(tool_path: Path) -> Tuple[Optional[str], Optional[Path]]:
    """Derive module name from tool path for proper relative imports.

    Tools are located under .ai/tools/<module_path>.py
    E.g., .ai/tools/rye/core/registry/registry.py -> rye.core.registry.registry

    Args:
        tool_path: Absolute path to the tool .py file

    Returns:
        Tuple of (module_name, tools_root) or (None, None) if not found
    """
    parts = tool_path.resolve().parts

    # Find ".../.ai/tools/<pkg>/<...>/<module>.py"
    for i in range(len(parts) - 2):
        if parts[i] == ".ai" and parts[i + 1] == "tools":
            tools_root = Path(*parts[: i + 2])  # .../.ai/tools
            rel = Path(*parts[i + 2 :]).with_suffix("")  # rye/core/registry/registry
            module_name = rel.as_posix().replace("/", ".")
            return module_name, tools_root

    return None, None


async def run_tool(
    tool_path: str,
    action: str,
    params: Dict[str, Any],
    project_path: str,
) -> Dict[str, Any]:
    """Import and execute a tool module.

    Args:
        tool_path: Path to the tool .py file
        action: Action to execute
        params: Parameters dict
        project_path: Project root path

    Returns:
        Result dict from execute()
    """
    path = Path(tool_path)

    if not path.exists():
        return {"success": False, "error": f"Tool not found: {tool_path}"}

    # Derive module name for proper relative imports
    mod_name, tools_root = module_name_from_tool_path(path)

    if not mod_name:
        return {
            "success": False,
            "error": f"Cannot derive module name from tool_path={tool_path}. "
            "Tool must be under .ai/tools/ directory.",
        }

    # Add tools root to path for imports
    if tools_root and str(tools_root) not in sys.path:
        sys.path.insert(0, str(tools_root))

    # Add project path for project-level imports
    if project_path and project_path not in sys.path:
        sys.path.insert(0, project_path)

    try:
        mod = importlib.import_module(mod_name)
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import {mod_name}: {e}",
        }

    if not hasattr(mod, "execute"):
        return {
            "success": False,
            "error": f"Tool {mod_name} missing execute(action, project_path, params) function",
        }

    execute_fn = getattr(mod, "execute")

    try:
        # Call execute (handle both sync and async)
        if inspect.iscoroutinefunction(execute_fn):
            result = await execute_fn(action, project_path, params)
        else:
            result = execute_fn(action, project_path, params)

        # Normalize result
        if isinstance(result, dict):
            if "success" in result:
                return result
            elif "error" in result:
                return {"success": False, **result}
            else:
                return {"success": True, "data": result}
        else:
            return {"success": True, "data": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def main_async():
    """Async main entry point."""
    parser = argparse.ArgumentParser(
        description="Execute a Python tool's execute() function"
    )
    parser.add_argument("tool_path", help="Path to the tool .py file")
    parser.add_argument("--action", required=True, help="Action to execute")
    parser.add_argument("--params", default="{}", help="JSON parameters")
    parser.add_argument("--project-path", required=True, help="Project root path")

    args = parser.parse_args()

    try:
        params = json.loads(args.params or "{}")
    except json.JSONDecodeError as e:
        result = {"success": False, "error": f"Invalid JSON params: {e}"}
        print(json.dumps(result))
        sys.exit(1)

    result = await run_tool(
        tool_path=args.tool_path,
        action=args.action,
        params=params,
        project_path=args.project_path,
    )

    print(json.dumps(result))
    sys.exit(0 if result.get("success") else 1)


def main():
    """CLI entry point."""
    try:
        asyncio.run(main_async())
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
