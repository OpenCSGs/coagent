from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Generic

from typing_extensions import TypeVar

from .types import FunctionToolCallProgressItem, ToolCallProgressItem, StreamEvent

TData = TypeVar("TData", default=Any)


@dataclass
class RunContext(Generic[TData]):
    """This wraps the data object that you passed to `AgentSpec.run()`.

    NOTE: Contexts are not passed to the LLM. They're a way to pass dependencies and data to code
    you implement, like tool functions, callbacks, hooks, etc.
    """

    _data: TData | None = field(default=None)
    """The data object (or None), passed by you to `AgentSpec.run()`"""

    _queue: asyncio.Queue | None = field(default=None, repr=False)
    """An optional event queue that background tasks write to."""

    tool: ToolData | None = field(default=None)
    """Information about the tool being invoked, if any."""

    parent: RunContext[TData] | None = field(default=None)
    """The parent context, if this is a nested run (e.g. agents as tools)."""

    @classmethod
    def with_tool(
        cls, parent: RunContext[TData], *, name: str, call_id: str, arguments: str
    ) -> RunContext[TData]:
        """Create a new context for a tool invocation."""
        return cls(
            parent=parent,
            tool=ToolData(name=name, call_id=call_id, arguments=arguments),
        )

    @property
    def data(self) -> TData | None:
        """Get the underlying data object."""
        if self._data:
            return self._data
        if self.parent:
            return self.parent.data
        return None

    @property
    def queue(self) -> asyncio.Queue | None:
        """Get the underlying event queue."""
        if self._queue:
            return self._queue
        if self.parent:
            return self.parent.queue
        return None

    def report_progress(
        self, progress: float = 0, total: float = 0, message: str = ""
    ) -> None:
        """Report a progress event to the event queue."""
        event = ToolCallProgressItem(
            raw_item=FunctionToolCallProgressItem(
                call_id=self.tool.call_id if self.tool else "",
                progress=progress,
                total=total,
                message=message,
                type="function_call_progress",
            ),
            type="tool_call_progress_item",
        )
        if self.queue:
            self.queue.put_nowait(event)


@dataclass
class ToolData:
    name: str
    """The name of the tool being invoked."""

    call_id: str
    """The ID of the tool call."""

    arguments: str
    """The raw arguments string of the tool call."""
