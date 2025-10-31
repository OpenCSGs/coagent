from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from coagent.core import Address, BaseAgent

from .context import RunContext
from .messages import (
    InputHistory,
    InputMessage,
    MessageOutputItem,
    OutputMessage,
    ToolCallItem,
    ToolCallOutputItem,
    ToolCallProgressItem,
)


@dataclass
class Subagent:
    type: str
    """The type of the subagent."""

    tool_name: str | None = field(default=None, init=False)
    """The name of the subagent tool."""

    tool_description: str | None = field(default=None, init=False)
    """A description of the subagent tool."""

    def as_tool(
        self, name: str | None = None, description: str | None = None
    ) -> Subagent:
        self.tool_name = name
        self.tool_description = description
        return self


class SubagentTool:
    """A wrapper class that allows an agent to be used as a tool by a host agent."""

    def __init__(self, host_agent: BaseAgent, subagent: Subagent):
        self.host_agent: BaseAgent = host_agent
        self.subagent: Subagent = subagent

    def as_tool(self) -> Callable:
        async def run(ctx: RunContext, input: str) -> str:
            addr = Address(name=self.subagent.type, id=self.host_agent.address.id)
            msg = InputHistory(messages=[InputMessage(role="user", content=input)])
            result = await self.host_agent.channel.publish(
                addr, msg.encode(), stream=True
            )

            final_output = ""
            parent_tool_name = ctx.full_tool_name

            try:
                async for chunk in result:
                    msg = OutputMessage.decode(chunk)
                    i = msg.item
                    match i:
                        case MessageOutputItem():
                            final_output += i.raw_item.content[0].text

                        case ToolCallItem():
                            # Use the full tool name that includes its parent agent (as tool) in the stream events.
                            # This is pretty useful for debugging and understanding the tool call hierarchy.
                            if parent_tool_name:
                                i.raw_item.name = (
                                    f"{parent_tool_name}/{i.raw_item.name}"
                                )

                            final_output = ""  # Reset tool output on intermediate updates. We only want the final output.
                            ctx.put_event(i)

                        case ToolCallProgressItem():
                            final_output = ""
                            ctx.put_event(i)

                        case ToolCallOutputItem():
                            final_output = ""
                            ctx.put_event(i)
            except Exception as exc:
                return f"Error: {exc}"
            else:
                return final_output

        run.__name__ = (
            self.subagent.tool_name
            or f"{self.subagent.type}.{self.host_agent.address.id}"
        )
        run.__doc__ = self.subagent.tool_description or ""
        return run
