# rye:validated:2026-02-09T12:00:00Z:placeholder
"""Read a file from the project workspace."""

import argparse
import json
import sys
from pathlib import Path

__version__ = "1.0.0"
__tool_type__ = "python"
__executor_id__ = "rye/core/runtimes/python_runtime"
__category__ = "rye/file-system"
__tool_description__ = "Read a file from the project workspace"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "File path relative to project root or absolute (must be inside project)",
        },
        "encoding": {"type": "string", "default": "utf-8"},
        "max_bytes": {"type": "integer", "default": 200000},
    },
    "required": ["path"],
}


def execute(params: dict, project_path: str) -> dict:
    project = Path(project_path).resolve()
    file_path = Path(params["path"])
    encoding = params.get("encoding", "utf-8")
    max_bytes = params.get("max_bytes", 200000)

    if not file_path.is_absolute():
        file_path = project / file_path
    file_path = file_path.resolve()

    if not file_path.is_relative_to(project):
        return {"success": False, "error": "Path is outside the project workspace"}

    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    if file_path.is_dir():
        return {"success": False, "error": "Path is a directory, not a file"}

    try:
        raw = file_path.read_bytes()
        truncated = len(raw) > max_bytes
        if truncated:
            raw = raw[:max_bytes]
        content = raw.decode(encoding)
        return {
            "success": True,
            "path": str(file_path),
            "content": content,
            "bytes": len(raw),
            "truncated": truncated,
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
