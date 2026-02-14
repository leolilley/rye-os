# rye:signed:2026-02-14T00:28:39Z:cffcbf912650e9fd3625747c494896be6fdae262eb97e1394fdde4c9b21dfb07:IvKgDuJlqP9oAXSYvSA6m1YMwAiLEtGo56HVa2hcON-_PFyNCsLnsjpAnCSRaqnmT9RNhXtSWKB9bwactyz3Bg==:440443d0858f0199
"""
errors.py: Typed exceptions for the thread system.

All Part 2 modules raise typed exceptions instead of returning
None/False/empty dicts. Classified by error_classification.yaml.
"""

__version__ = "1.0.0"
__tool_type__ = "python"
__category__ = "rye/agent/threads"
__tool_description__ = "Typed exceptions for the thread system"


class ThreadSystemError(Exception):
    """Base for all thread system errors."""


class TranscriptCorrupt(ThreadSystemError):
    """Transcript JSONL has unparseable lines."""

    def __init__(self, path: str, line_no: int, raw_line: str):
        self.path = path
        self.line_no = line_no
        super().__init__(f"Corrupt transcript at {path}:{line_no}")


class ResumeImpossible(ThreadSystemError):
    """Cannot resume thread — insufficient recovery data."""

    def __init__(self, thread_id: str, reason: str):
        self.thread_id = thread_id
        self.reason = reason
        super().__init__(f"Cannot resume {thread_id}: {reason}")


class ThreadNotFound(ThreadSystemError):
    """No registry entry or completion event for thread."""

    def __init__(self, thread_id: str, context: str = ""):
        self.thread_id = thread_id
        super().__init__(
            f"Thread not found: {thread_id}" + (f" ({context})" if context else "")
        )


class CheckpointFailed(ThreadSystemError):
    """State checkpoint write failed. Thread must stop."""

    def __init__(self, thread_id: str, trigger: str, cause: Exception):
        self.thread_id = thread_id
        self.trigger = trigger
        self.cause = cause
        super().__init__(f"Checkpoint failed for {thread_id} at {trigger}: {cause}")
