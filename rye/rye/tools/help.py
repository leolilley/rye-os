"""Help tool - get usage guidance for RYE MCP."""

import logging
from typing import Any, Dict, Optional

from rye.constants import ItemType, Action

logger = logging.getLogger(__name__)


class HelpTool:
    """Provide usage guidance for RYE MCP tools."""

    def __init__(self, user_space: Optional[str] = None):
        """Initialize help tool."""
        self.user_space = user_space

    async def handle(self, **kwargs) -> Dict[str, Any]:
        """Handle help request."""
        topic = kwargs.get("topic", "overview")

        logger.debug(f"Help: topic={topic}")

        topics = {
            "overview": self._overview,
            Action.SEARCH: self._search_help,
            Action.LOAD: self._load_help,
            Action.EXECUTE: self._execute_help,
            Action.SIGN: self._sign_help,
            "directives": self._directives_help,
            "tools": self._tools_help,
            "knowledge": self._knowledge_help,
        }

        handler = topics.get(topic)
        if handler:
            return {"status": "success", "topic": topic, "content": handler()}
        else:
            return {
                "status": "success",
                "topic": "available_topics",
                "content": f"Available topics: {', '.join(topics.keys())}",
            }

    def _overview(self) -> str:
        return """# RYE MCP Overview

RYE provides 5 MCP tools for managing AI agent items:

## The 5 Tools

| Tool | Purpose |
|------|---------|
| `search` | Find items by keywords |
| `load` | Load item content for inspection |
| `execute` | Run directives/tools, load knowledge |
| `sign` | Validate and sign items |
| `help` | Get usage guidance |

## The 3 Item Types

| Type | Location | Format |
|------|----------|--------|
| `directive` | `.ai/directives/` | XML in Markdown |
| `tool` | `.ai/tools/` | Python, YAML, etc. |
| `knowledge` | `.ai/knowledge/` | Markdown + frontmatter |

## Tool Spaces (Precedence Order)

1. **Project** - `.ai/` in current project (highest priority)
2. **User** - `~/.ai/` user space
3. **System** - Bundled with RYE (lowest priority)
"""

    def _search_help(self) -> str:
        return """# Search Tool

Find items by keywords across project, user, and system spaces.

## Parameters

- `item_type`: "directive" | "tool" | "knowledge"
- `query`: Search keywords
- `project_path`: Path to project root
- `source`: "project" | "user" | "system" | "all"
- `limit`: Max results (default: 10)

## Example

```python
search(
    item_type="tool",
    query="git status",
    project_path="/path/to/project",
    source="all"
)
```
"""

    def _load_help(self) -> str:
        return """# Load Tool

Load item content for inspection or copy between locations.

## Parameters

- `item_type`: "directive" | "tool" | "knowledge"
- `item_id`: Item identifier
- `project_path`: Path to project root
- `source`: "project" | "user" | "system"
- `destination`: Optional - "project" | "user" (for copying)

## Example

```python
load(
    item_type="directive",
    item_id="research_topic",
    source="user",
    destination="project"  # Copy to project
)
```
"""

    def _execute_help(self) -> str:
        return """# Execute Tool

Execute items - directives, tools, or knowledge entries.

## Parameters

- `item_type`: "directive" | "tool" | "knowledge"
- `item_id`: Item identifier
- `project_path`: Path to project root
- `parameters`: Action-specific parameters
- `dry_run`: Validate without executing

## Execution Behavior

- **Directive**: Returns parsed XML for agent to follow
- **Tool**: Executes via Lilux primitives
- **Knowledge**: Returns content for context

## Example

```python
execute(
    item_type="tool",
    item_id="git_status",
    project_path="/path/to/project",
    parameters={"branch": "main"}
)
```
"""

    def _sign_help(self) -> str:
        return """# Sign Tool

Validate and cryptographically sign items.

## Parameters

- `item_type`: "directive" | "tool" | "knowledge"
- `item_id`: Item identifier
- `project_path`: Path to project root
- `location`: "project" | "user"

## Purpose

- Validates item structure
- Computes integrity hash
- Adds signature comment to file

## Example

```python
execute(
    item_type="directive",
    action="sign",
    item_id="research_topic",
    project_path="/path/to/project"
)
```
"""

    def _directives_help(self) -> str:
        return """# Directives

Directives are XML-based workflow instructions wrapped in Markdown.

## Location

`.ai/directives/{category}/{name}.md`

## Structure

```markdown
<!-- rye:validated:timestamp:hash -->

# Directive Name

```xml
<directive name="example" version="1.0.0">
  <metadata>
    <description>What this directive does</description>
    <category>utility</category>
    <model tier="general">Model guidance</model>
  </metadata>

  <inputs>
    <input name="param1" type="string" required="true">Description</input>
  </inputs>

  <process>
    <step name="step1">
      <action>What to do</action>
    </step>
  </process>

  <outputs>
    <success>Expected outcome</success>
  </outputs>
</directive>
```
```
"""

    def _tools_help(self) -> str:
        return """# Tools

Tools are executable scripts that delegate to Lilux primitives.

## Location

`.ai/tools/{category}/{name}.py` (or .yaml, .js, .sh, etc.)

## Python Tool Structure

```python
#!/usr/bin/env python3
# rye:validated:timestamp:hash
\"\"\"Tool description.\"\"\"

__version__ = "1.0.0"
__tool_type__ = "python"
__executor_id__ = "python_runtime"
__category__ = "utility"

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "param1": {"type": "string"}
    }
}

def main(**kwargs) -> dict:
    \"\"\"Tool implementation.\"\"\"
    return {"result": "success"}
```

## Executor Chain

Tools declare `__executor_id__` to specify how they execute:
- `None`: Primitive (direct execution)
- `"subprocess"`: Shell execution
- `"python_runtime"`: Python interpreter
- Custom runtime IDs
"""

    def _knowledge_help(self) -> str:
        return """# Knowledge

Knowledge entries are Markdown files with YAML frontmatter.

## Location

`.ai/knowledge/{category}/{id}.md`

## Structure

```markdown
<!-- rye:validated:timestamp:hash -->
---
id: unique-id
title: Entry Title
entry_type: pattern | learning | reference | decision
category: category-name
version: "1.0.0"
tags: [tag1, tag2]
---

# Entry Title

Content goes here...
```

## Entry Types

- **pattern**: Reusable design patterns
- **learning**: Lessons learned
- **reference**: Reference documentation
- **decision**: Architectural decisions
- **concept**: Core concepts
- **procedure**: Step-by-step procedures
"""
