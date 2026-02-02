"""Markdown frontmatter parser for knowledge entries.

Extracts YAML frontmatter and separates it from body content.
"""

import re
from typing import Any, Dict, Optional


def parse(content: str) -> Dict[str, Any]:
    """Parse markdown with YAML frontmatter.
    
    Returns parsed frontmatter dict + body content.
    """
    result: Dict[str, Any] = {
        "body": "",
        "raw": content,
    }
    
    if not content.startswith("---"):
        return result
    
    lines = content.split("\n")
    frontmatter_end = None
    
    # Find closing ---
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            frontmatter_end = i
            break
    
    if not frontmatter_end:
        return result
    
    # Parse frontmatter lines
    for line in lines[1:frontmatter_end]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        
        if ":" not in line:
            continue
        
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        
        # Handle list values
        if value.startswith("[") and value.endswith("]"):
            # Parse list
            items = value[1:-1].split(",")
            value = [item.strip().strip("'\"") for item in items if item.strip()]
        
        result[key] = value
    
    # Extract body
    body_start = frontmatter_end + 1
    if body_start < len(lines):
        result["body"] = "\n".join(lines[body_start:]).strip()
    
    return result
