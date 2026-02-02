"""RYE MCP Constants

Centralized constants for item types and tool actions.
"""


class ItemType:
    """Item type constants."""

    DIRECTIVE = "directive"
    TOOL = "tool"
    KNOWLEDGE = "knowledge"

    ALL = [DIRECTIVE, TOOL, KNOWLEDGE]

    # Type directory mappings
    TYPE_DIRS = {
        DIRECTIVE: "directives",
        TOOL: "tools",
        KNOWLEDGE: "knowledge",
    }


class Action:
    """Tool action constants."""

    SEARCH = "search"
    SIGN = "sign"
    LOAD = "load"
    EXECUTE = "execute"
    HELP = "help"

    ALL = [SEARCH, SIGN, LOAD, EXECUTE, HELP]
