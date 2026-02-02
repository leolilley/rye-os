"""
Registry for language-specific signature formats.

Loads signature format configuration from extractor tools across 3-tier space.
"""

import ast
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rye.utils.path_utils import (
    get_user_space,
    get_system_space,
    get_extractor_search_paths,
)

logger = logging.getLogger(__name__)

# Global cache: extension -> signature format
_signature_formats: Optional[Dict[str, Dict[str, Any]]] = None


def get_signature_format(
    file_path: Path, project_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Get signature format for a file based on its extension.

    Args:
        file_path: Path to the file
        project_path: Optional project path for extractor discovery

    Returns:
        Signature format dict with 'prefix' and 'after_shebang' keys.
    """
    global _signature_formats

    if _signature_formats is None:
        _signature_formats = _load_signature_formats(project_path)

    ext = file_path.suffix.lower()
    format_config = _signature_formats.get(ext)

    if format_config:
        return format_config

    # Default to Python-style comments
    return {"prefix": "#", "after_shebang": True}


def _load_signature_formats(
    project_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Load signature formats from all extractors."""
    formats = {}
    search_paths = get_extractor_search_paths(project_path)

    for extractors_dir in search_paths:
        if not extractors_dir.exists():
            continue

        for file_path in extractors_dir.glob("*_extractor.py"):
            if file_path.name.startswith("_"):
                continue

            extractor_data = _extract_format_from_file(file_path)
            if not extractor_data:
                continue

            sig_format = extractor_data.get(
                "signature_format", {"prefix": "#", "after_shebang": True}
            )

            for ext in extractor_data.get("extensions", []):
                # Only set if not already set (precedence: project > user > system)
                if ext.lower() not in formats:
                    formats[ext.lower()] = sig_format

    logger.debug(f"Loaded signature formats for extensions: {list(formats.keys())}")
    return formats


def _extract_format_from_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract EXTENSIONS and SIGNATURE_FORMAT from an extractor file using AST."""
    try:
        content = file_path.read_text()
        tree = ast.parse(content)

        result = {"extensions": [], "signature_format": None}

        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    if target.id == "EXTENSIONS" and isinstance(node.value, ast.List):
                        result["extensions"] = [
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant)
                            and isinstance(elt.value, str)
                        ]
                    elif target.id == "SIGNATURE_FORMAT" and isinstance(
                        node.value, ast.Dict
                    ):
                        result["signature_format"] = ast.literal_eval(node.value)

        return result if result["extensions"] else None
    except Exception as e:
        logger.warning(f"Failed to extract format from {file_path}: {e}")
        return None


def clear_signature_formats_cache():
    """Clear the signature formats cache."""
    global _signature_formats
    _signature_formats = None
