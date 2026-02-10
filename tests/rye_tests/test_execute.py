"""Tests for execute tool."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from rye.tools.execute import ExecuteTool


@pytest.fixture
def temp_project(_setup_user_space):
    """Create temporary project with test items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        ai_dir = project_root / ".ai"

        # Create directive with proper markdown+xml format
        directives_dir = ai_dir / "directives"
        directives_dir.mkdir(parents=True)
        (directives_dir / "workflow.md").write_text('''# Workflow Directive

```xml
<directive name="workflow" version="1.0.0">
<process>
<step name="step1">Do something</step>
</process>
</directive>
```
''')

        # Create tool with proper metadata
        tools_dir = ai_dir / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "mytool.py").write_text('''
__version__ = "1.0.0"
__tool_type__ = "primitive"
__executor_id__ = None
__category__ = "test"

def main():
    print('tool')
''')

        # Create knowledge
        knowledge_dir = ai_dir / "knowledge"
        knowledge_dir.mkdir(parents=True)
        (knowledge_dir / "entry.md").write_text(
            "---\ntitle: Test Entry\nid: entry\n---\n\nContent here"
        )

        from rye.utils.metadata_manager import MetadataManager
        from rye.constants import ItemType

        for directive_file in (ai_dir / "directives").glob("*.md"):
            content = directive_file.read_text()
            signed = MetadataManager.sign_content(ItemType.DIRECTIVE, content)
            directive_file.write_text(signed)

        for tool_file in (ai_dir / "tools").rglob("*.py"):
            content = tool_file.read_text()
            signed = MetadataManager.sign_content(
                ItemType.TOOL, content, file_path=tool_file, project_path=project_root
            )
            tool_file.write_text(signed)

        for knowledge_file in (ai_dir / "knowledge").glob("*.md"):
            content = knowledge_file.read_text()
            signed = MetadataManager.sign_content(ItemType.KNOWLEDGE, content)
            knowledge_file.write_text(signed)

        yield project_root


@pytest.mark.asyncio
class TestExecuteTool:
    """Test execute tool."""

    async def test_execute_directive(self, temp_project):
        """Execute directive."""
        tool = ExecuteTool("")
        result = await tool.handle(
            item_type="directive",
            item_id="workflow",
            project_path=str(temp_project),
        )

        assert result["status"] == "success"
        assert result["type"] == "directive"
        assert "metadata" in result

    async def test_execute_tool(self, temp_project):
        """Execute tool - primitives without known type return error."""
        tool = ExecuteTool("")
        result = await tool.handle(
            item_type="tool",
            item_id="mytool",
            project_path=str(temp_project),
        )

        # The tool is a primitive with executor_id=None but not a known primitive
        # (subprocess, http_client), so it returns an error
        assert result["status"] == "error"
        assert "Unknown primitive" in result["error"]

    async def test_execute_knowledge(self, temp_project):
        """Execute/load knowledge."""
        tool = ExecuteTool("")
        result = await tool.handle(
            item_type="knowledge",
            item_id="entry",
            project_path=str(temp_project),
        )

        assert result["status"] == "success"
        assert result["type"] == "knowledge"
        assert "Test Entry" in result["data"].get("title", result["data"].get("raw", ""))

    async def test_dry_run_directive(self, temp_project):
        """Dry run directive."""
        tool = ExecuteTool("")
        result = await tool.handle(
            item_type="directive",
            item_id="workflow",
            project_path=str(temp_project),
            dry_run=True,
        )

        assert result["status"] == "validation_passed"

    async def test_dry_run_tool(self, temp_project):
        """Dry run tool."""
        tool = ExecuteTool("")
        result = await tool.handle(
            item_type="tool",
            item_id="mytool",
            project_path=str(temp_project),
            dry_run=True,
        )

        assert result["status"] == "validation_passed"

    async def test_execute_nonexistent_directive(self, temp_project):
        """Error on nonexistent directive."""
        tool = ExecuteTool("")
        result = await tool.handle(
            item_type="directive",
            item_id="nonexistent",
            project_path=str(temp_project),
        )

        assert result["status"] == "error"

    async def test_execute_with_parameters(self, temp_project):
        """Execute with parameters - unknown primitive returns error."""
        tool = ExecuteTool("")
        result = await tool.handle(
            item_type="tool",
            item_id="mytool",
            project_path=str(temp_project),
            parameters={"arg1": "value1"},
        )

        # Unknown primitive returns error (mytool is not subprocess/http_client)
        assert result["status"] == "error"
