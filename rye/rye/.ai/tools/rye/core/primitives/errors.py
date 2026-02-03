# rye:validated:2026-02-03T01:19:05+00:00:d216eee8a282a445280233d27619102bc627cd7c61814bbae970ec9cf9810c92
"""
Tool chain error handling with full execution context.

Provides comprehensive error types for tool execution with chain context,
config paths, and validation errors for LLM-actionable error responses.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ValidationError:
    """A single validation error for a field."""

    field: str
    error: str
    value: Optional[Any] = None


@dataclass
class FailedToolContext:
    """Context about where a tool chain failed."""

    tool_id: str
    config_path: str
    validation_errors: List[ValidationError] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolChainError(Exception):
    """
    Error that occurs in a tool chain with full execution context.

    Includes the chain path, which tool failed, its config path,
    and validation errors for LLM-actionable error responses.
    """

    def __init__(
        self,
        code: str,
        message: str,
        chain: List[str],
        failed_at: FailedToolContext,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize ToolChainError.

        Args:
            code: Error code (e.g., "TOOL_CHAIN_FAILED", "CONFIG_VALIDATION_ERROR")
            message: Human-readable error message
            chain: List of tool IDs in the chain (e.g., ["anthropic_thread", "anthropic_messages", "http_client"])
            failed_at: Context about where the failure occurred
            cause: Optional underlying exception
        """
        self.code = code
        self.message = message
        self.chain = chain
        self.failed_at = failed_at
        self.cause = cause

        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format a user-friendly error message."""
        parts = [
            f"[{self.code}] {self.message}",
            f"  Failed tool: {self.failed_at.tool_id}",
            f"  Config path: {self.failed_at.config_path}",
        ]

        if self.failed_at.validation_errors:
            parts.append("  Validation errors:")
            for err in self.failed_at.validation_errors:
                parts.append(f"    - {err.field}: {err.error}")

        if self.cause:
            parts.append(f"  Underlying error: {type(self.cause).__name__}: {self.cause}")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dict for JSON serialization.

        Returns a structure suitable for LLM consumption:
        {
            "code": "...",
            "message": "...",
            "chain": [...],
            "failed_at": {
                "tool_id": "...",
                "config_path": "...",
                "validation_errors": [...]
            },
            "cause": {"code": "...", "message": "..."}
        }
        """
        return {
            "code": self.code,
            "message": self.message,
            "chain": self.chain,
            "failed_at": {
                "tool_id": self.failed_at.tool_id,
                "config_path": self.failed_at.config_path,
                "validation_errors": [
                    {"field": e.field, "error": e.error, "value": e.value}
                    for e in self.failed_at.validation_errors
                ],
            },
            "cause": (
                {
                    "code": self.cause.__dict__.get("code", "UNKNOWN"),
                    "message": str(self.cause),
                }
                if self.cause
                else None
            ),
        }


class ConfigValidationError(Exception):
    """Error validating tool configuration."""

    def __init__(self, tool_id: str, errors: List[ValidationError]):
        """
        Initialize ConfigValidationError.

        Args:
            tool_id: ID of the tool with config errors
            errors: List of validation errors
        """
        self.tool_id = tool_id
        self.errors = errors

        parts = [f"Config validation failed for '{tool_id}':"]
        for err in errors:
            parts.append(f"  - {err.field}: {err.error}")

        super().__init__("\n".join(parts))
