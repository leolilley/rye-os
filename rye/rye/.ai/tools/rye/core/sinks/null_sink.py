# rye:signed:2026-02-12T23:55:37Z:b0b295fadfbf40e9e679078af1d71e6fb605e720838914d8f4a8da1fde0cc2ad:esgymCu_fS93KqIYYJ8BStVbzZRwjwF-rtKtqxTEr2Zb4-Y50u5cSSW1q4KE68ApP3xxhOgWm5ed6ndtUYu-DQ==:440443d0858f0199
__tool_type__ = "runtime"
__version__ = "1.0.0"
__executor_id__ = "python"
__category__ = "rye/core/sinks"
__tool_description__ = "Null sink - discards all events without processing"


class NullSink:
    """Discard all events."""

    async def write(self, event: str) -> None:
        """Discard event."""
        pass

    async def close(self) -> None:
        """No-op close."""
        pass
