# rye:signed:2026-02-14T00:36:33Z:8e1ab83b0df0e582e7c00467338e11bbfd40ef1932a98481f8733abecccc38d3:lChWmZIRMMsyo1b5MRAWGR9SlBL4h0iMoPPTga_HY47fg2gyLFgWphc-4vhBEHIaBVHesvrP7PDXbOYHRWrBCg==:440443d0858f0199
"""Telemetry tools package."""

__version__ = "1.0.0"
__tool_type__ = "python"
__category__ = "rye/core/telemetry"
__tool_description__ = "Telemetry tools package"

from .mcp_logs import get_logs, get_log_stats

__all__ = ["get_logs", "get_log_stats"]
