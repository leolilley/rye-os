"""Lilux primitives: stateless execution units."""

from lilux.primitives.errors import (
    AuthenticationRequired,
    ConfigurationError,
    IntegrityError,
    LockfileError,
    RefreshError,
    ToolExecutionError,
    ValidationError,
)
from lilux.primitives.http_client import HttpClientPrimitive, HttpResult, ReturnSink
from lilux.primitives.integrity import (
    compute_directive_integrity,
    compute_knowledge_integrity,
    compute_tool_integrity,
)
from lilux.primitives.lockfile import Lockfile, LockfileManager, LockfileRoot
from lilux.primitives.subprocess import SubprocessPrimitive, SubprocessResult

__all__ = [
    # Errors
    "ValidationError",
    "ToolExecutionError",
    "IntegrityError",
    "LockfileError",
    "ConfigurationError",
    "AuthenticationRequired",
    "RefreshError",
    # Integrity
    "compute_tool_integrity",
    "compute_directive_integrity",
    "compute_knowledge_integrity",
    # Lockfile
    "LockfileRoot",
    "Lockfile",
    "LockfileManager",
    # Subprocess
    "SubprocessResult",
    "SubprocessPrimitive",
    # HTTP Client
    "HttpResult",
    "HttpClientPrimitive",
    "ReturnSink",
]
