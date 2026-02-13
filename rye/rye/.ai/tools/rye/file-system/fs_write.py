# rye:signed:2026-02-13T08:13:10Z:731d7d64c6b9447abc503e559b791b2a5edeb256b15d358360b78bb555bd7e38:LgQgLRB5lT0ArWIayTzbKSBp0rMr5ZMAVTJ29QNhJgEvcsbMQzcjuTSCsTuPDXpDelXPIssa8qGkPnHpGKPrCA==:440443d0858f0199
"""Write content to a file in the project workspace."""

import argparse
import json
import sys
from pathlib import Path

__version__ = "1.0.0"
__tool_type__ = "python"
__executor_id__ = "rye/core/runtimes/python_script_runtime"
__category__ = "rye/file-system"
__tool_description__ = "Write content to a file in the project workspace"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "File path relative to project root or absolute (must be inside project)",
        },
        "content": {"type": "string", "description": "Content to write"},
        "mode": {
            "type": "string",
            "enum": ["overwrite", "append"],
            "default": "overwrite",
        },
        "create_dirs": {"type": "boolean", "default": True},
        "encoding": {"type": "string", "default": "utf-8"},
    },
    "required": ["path", "content"],
}


def execute(params: dict, project_path: str) -> dict:
    project = Path(project_path).resolve()
    file_path = Path(params["path"])
    content = params["content"]
    mode = params.get("mode", "overwrite")
    create_dirs = params.get("create_dirs", True)
    encoding = params.get("encoding", "utf-8")

    if not file_path.is_absolute():
        file_path = project / file_path
    file_path = file_path.resolve()

    if not file_path.is_relative_to(project):
        return {"success": False, "error": "Path is outside the project workspace"}

    try:
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        encoded = content.encode(encoding)
        if mode == "append":
            with open(file_path, "ab") as f:
                f.write(encoded)
        else:
            with open(file_path, "wb") as f:
                f.write(encoded)

        return {
            "success": True,
            "path": str(file_path),
            "bytes_written": len(encoded),
            "mode": mode,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", required=True)
    parser.add_argument("--project-path", required=True)
    args = parser.parse_args()
    result = execute(json.loads(args.params), args.project_path)
    print(json.dumps(result))
