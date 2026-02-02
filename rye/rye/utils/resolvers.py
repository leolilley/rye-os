"""
Path Resolution Utilities

Finds directives, tools, and knowledge entries across 3-tier space system:
  1. Project space: {project}/.ai/ (highest priority)
  2. User space: ~/.ai/ or $USER_SPACE
  3. System space: site-packages/rye/.ai/ (lowest priority, immutable)
"""

from pathlib import Path
from typing import Optional, Tuple, List
import logging

from rye.utils.extensions import get_tool_extensions
from rye.utils.path_utils import (
    get_user_space,
    get_system_space,
    get_project_type_path,
    get_user_type_path,
    get_system_type_path,
)
from rye.constants import ItemType

logger = logging.getLogger(__name__)


class DirectiveResolver:
    """Resolve directive file paths across 3-tier space."""

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = project_path or Path.cwd()
        self.user_space = get_user_space()
        self.system_space = get_system_space()

    def get_search_paths(self) -> List[Tuple[Path, str]]:
        """Get search paths in precedence order with space labels."""
        paths = []

        # Project space (highest priority)
        project_dir = get_project_type_path(self.project_path, ItemType.DIRECTIVE)
        if project_dir.exists():
            paths.append((project_dir, "project"))

        # User space
        user_dir = get_user_type_path(ItemType.DIRECTIVE)
        if user_dir.exists():
            paths.append((user_dir, "user"))

        # System space (lowest priority)
        system_dir = get_system_type_path(ItemType.DIRECTIVE)
        if system_dir.exists():
            paths.append((system_dir, "system"))

        return paths

    def resolve(self, directive_name: str) -> Optional[Path]:
        """Find directive file in project > user > system order."""
        for search_dir, _ in self.get_search_paths():
            for file_path in search_dir.rglob(f"{directive_name}.md"):
                if file_path.is_file():
                    return file_path
        return None

    def resolve_with_space(self, directive_name: str) -> Optional[Tuple[Path, str]]:
        """Find directive and return (path, space) tuple."""
        for search_dir, space in self.get_search_paths():
            for file_path in search_dir.rglob(f"{directive_name}.md"):
                if file_path.is_file():
                    return (file_path, space)
        return None


class ToolResolver:
    """Resolve tool file paths across 3-tier space."""

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = project_path or Path.cwd()
        self.user_space = get_user_space()
        self.system_space = get_system_space()

    def get_search_paths(self) -> List[Tuple[Path, str]]:
        """Get search paths in precedence order with space labels."""
        paths = []

        # Project space (highest priority)
        project_dir = get_project_type_path(self.project_path, ItemType.TOOL)
        if project_dir.exists():
            paths.append((project_dir, "project"))

        # User space
        user_dir = get_user_type_path(ItemType.TOOL)
        if user_dir.exists():
            paths.append((user_dir, "user"))

        # System space (lowest priority)
        system_dir = get_system_type_path(ItemType.TOOL)
        if system_dir.exists():
            paths.append((system_dir, "system"))

        return paths

    def resolve(self, tool_name: str) -> Optional[Path]:
        """Find tool file in project > user > system order."""
        extensions = get_tool_extensions(self.project_path)

        for search_dir, _ in self.get_search_paths():
            for ext in extensions:
                for file_path in search_dir.rglob(f"{tool_name}{ext}"):
                    if file_path.is_file():
                        return file_path
        return None

    def resolve_with_space(self, tool_name: str) -> Optional[Tuple[Path, str]]:
        """Find tool and return (path, space) tuple."""
        extensions = get_tool_extensions(self.project_path)

        for search_dir, space in self.get_search_paths():
            for ext in extensions:
                for file_path in search_dir.rglob(f"{tool_name}{ext}"):
                    if file_path.is_file():
                        return (file_path, space)
        return None


class KnowledgeResolver:
    """Resolve knowledge entry file paths across 3-tier space."""

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = project_path or Path.cwd()
        self.user_space = get_user_space()
        self.system_space = get_system_space()

    def get_search_paths(self) -> List[Tuple[Path, str]]:
        """Get search paths in precedence order with space labels."""
        paths = []

        # Project space (highest priority)
        project_dir = get_project_type_path(self.project_path, ItemType.KNOWLEDGE)
        if project_dir.exists():
            paths.append((project_dir, "project"))

        # User space
        user_dir = get_user_type_path(ItemType.KNOWLEDGE)
        if user_dir.exists():
            paths.append((user_dir, "user"))

        # System space (lowest priority)
        system_dir = get_system_type_path(ItemType.KNOWLEDGE)
        if system_dir.exists():
            paths.append((system_dir, "system"))

        return paths

    def resolve(self, entry_id: str) -> Optional[Path]:
        """Find knowledge entry in project > user > system order."""
        for search_dir, _ in self.get_search_paths():
            for file_path in search_dir.rglob(f"{entry_id}.md"):
                if file_path.is_file():
                    return file_path
        return None

    def resolve_with_space(self, entry_id: str) -> Optional[Tuple[Path, str]]:
        """Find knowledge entry and return (path, space) tuple."""
        for search_dir, space in self.get_search_paths():
            for file_path in search_dir.rglob(f"{entry_id}.md"):
                if file_path.is_file():
                    return (file_path, space)
        return None
